package com.statstriker.gateway;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.ExpectedCount.once;
import static org.springframework.test.web.client.ExpectedCount.twice;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.Primary;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.test.web.client.match.MockRestRequestMatchers;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.result.MockMvcResultMatchers;
import org.springframework.web.client.RestClient;

@SpringBootTest
@AutoConfigureMockMvc
@Import(GatewayOptimizationTests.MockEngineConfig.class)
@TestPropertySource(properties = {
    "statstriker.warmer-enabled=false",
    "statstriker.ai-engine-url=http://ai-engine.test"
})
class GatewayOptimizationTests {

    @TestConfiguration
    static class MockEngineConfig {
        private final RestClient.Builder sharedBuilder = RestClient.builder().baseUrl("http://ai-engine.test");

        @Bean
        MockRestServiceServer mockEngineServer() {
            return MockRestServiceServer.bindTo(sharedBuilder).ignoreExpectOrder(true).build();
        }

        @Bean
        @Primary
        RestClient testAiEngineRestClient(MockRestServiceServer server) {
            return sharedBuilder.build();
        }
    }

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private MockRestServiceServer mockServer;

    @BeforeEach
    void resetServer() {
        mockServer.reset();
    }

    @Test
    void chatCacheAndSessionMatchContextEnrichmentWork() throws Exception {
        String firstBody = """
            {
              "session_id": "s1",
              "message": "Analiza este partido",
              "match_context": {
                "id": "740740",
                "home": "Brentford",
                "away": "Everton",
                "competition": "Premier League",
                "kickoff": "2026-11-23T20:00Z",
                "status": "NS"
              }
            }
            """;

        mockServer.expect(once(), requestTo("http://ai-engine.test/api/chat"))
            .andExpect(method(HttpMethod.POST))
            .andExpect(MockRestRequestMatchers.jsonPath("$.match_context.home").value("Brentford"))
            .andRespond(withSuccess("""
                {"id":1,"answer":"Analisis Brentford vs Everton","active_rules":[],"context_quality":"good","sources":[],"analysis":{},"provider":"gemini:gemini-3.5-flash-lite"}
                """, MediaType.APPLICATION_JSON));

        mockServer.expect(once(), requestTo("http://ai-engine.test/api/chat"))
            .andExpect(method(HttpMethod.POST))
            .andExpect(MockRestRequestMatchers.jsonPath("$.match_context.id").value("740740"))
            .andExpect(MockRestRequestMatchers.jsonPath("$.match_context.away").value("Everton"))
            .andRespond(withSuccess("""
                {"id":2,"answer":"Igor Thiago lleva 1 gol en 5 partidos","active_rules":["estadisticas_jugador"],"context_quality":"good","sources":[],"analysis":{},"provider":"gemini:gemini-3.5-flash-lite"}
                """, MediaType.APPLICATION_JSON));

        mockServer.expect(once(), requestTo("http://ai-engine.test/api/health"))
            .andExpect(method(HttpMethod.GET))
            .andRespond(withSuccess("""
                {"status":"ok"}
                """, MediaType.APPLICATION_JSON));

        // Primera consulta con match_context
        mockMvc.perform(post("/api/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .content(firstBody))
            .andExpect(status().isOk())
            .andExpect(MockMvcResultMatchers.jsonPath("$.answer").value("Analisis Brentford vs Everton"));

        // Misma consulta repetida -> debe responder desde la caché sin volver a llamar ai-engine
        mockMvc.perform(post("/api/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .content(firstBody))
            .andExpect(status().isOk())
            .andExpect(MockMvcResultMatchers.jsonPath("$.answer").value("Analisis Brentford vs Everton"));

        // Pregunta de seguimiento SIN match_context -> Spring Boot debe reinyectar Brentford vs Everton
        String followUp = """
            {"session_id":"s1","message":"por cual apuesto y igor thiago hara gol?"}
            """;
        mockMvc.perform(post("/api/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .content(followUp))
            .andExpect(status().isOk())
            .andExpect(MockMvcResultMatchers.jsonPath("$.answer").value("Igor Thiago lleva 1 gol en 5 partidos"));

        String metricsJson = mockMvc.perform(get("/api/gateway/metrics"))
            .andExpect(status().isOk())
            .andReturn()
            .getResponse()
            .getContentAsString();
        mockServer.verify();
        assertThat(metricsJson).contains("\"chat_cache_hits\":1");
        assertThat(metricsJson).contains("\"enriched_followups\":1");
    }

    @Test
    void deleteHistoryEvictsSessionCacheAndFootballCacheWorks() throws Exception {
        mockServer.expect(once(), requestTo("http://ai-engine.test/api/football/leagues"))
            .andExpect(method(HttpMethod.GET))
            .andRespond(withSuccess("""
                {"leagues":[{"id":39,"name":"Premier League"}]}
                """, MediaType.APPLICATION_JSON));

        mockServer.expect(twice(), requestTo("http://ai-engine.test/api/chat"))
            .andExpect(method(HttpMethod.POST))
            .andRespond(withSuccess("""
                {"id":3,"answer":"Respuesta ok","active_rules":[],"context_quality":"good","sources":[],"analysis":{},"provider":"gemini:gemini-3.5-flash-lite"}
                """, MediaType.APPLICATION_JSON));

        mockServer.expect(once(), requestTo("http://ai-engine.test/api/history/s2"))
            .andExpect(method(HttpMethod.DELETE))
            .andRespond(withSuccess("""
                {"deleted":1}
                """, MediaType.APPLICATION_JSON));

        mockMvc.perform(get("/api/football/leagues")).andExpect(status().isOk());
        mockMvc.perform(get("/api/football/leagues")).andExpect(status().isOk());

        String body = """
            {"session_id":"s2","message":"como viene millonarios"}
            """;
        mockMvc.perform(post("/api/chat").contentType(MediaType.APPLICATION_JSON).content(body))
            .andExpect(status().isOk());

        mockMvc.perform(delete("/api/history/s2"))
            .andExpect(status().isOk())
            .andExpect(MockMvcResultMatchers.jsonPath("$.deleted").value(1));

        // Tras borrar historial, la consulta ya no está en caché y vuelve al motor IA
        mockMvc.perform(post("/api/chat").contentType(MediaType.APPLICATION_JSON).content(body))
            .andExpect(status().isOk());

        mockServer.verify();
    }

    @Test
    void healthIncludesSpringGatewayMetadata() throws Exception {
        mockServer.expect(once(), requestTo("http://ai-engine.test/api/health"))
            .andExpect(method(HttpMethod.GET))
            .andRespond(withSuccess("""
                {"status":"ok","llm":{"ready":true,"provider":"gemini","model":"gemini-3.5-flash-lite"},"vector_db":{"engine":"chromadb","documents":14}}
                """, MediaType.APPLICATION_JSON));

        mockMvc.perform(get("/api/health"))
            .andExpect(status().isOk())
            .andExpect(MockMvcResultMatchers.jsonPath("$.status").value("ok"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.gateway.engine").value("spring-boot"))
            .andExpect(MockMvcResultMatchers.jsonPath("$.gateway.virtual_threads").value(true));

        mockServer.verify();
    }

    @Test
    void historyBackupPreservesImagesWhenAiEngineDisconnects() throws Exception {
        mockServer.expect(once(), requestTo("http://ai-engine.test/api/chat"))
            .andExpect(method(HttpMethod.POST))
            .andRespond(withSuccess("""
                {"id":10,"answer":"Boleto analizado","active_rules":["analisis_imagen_apuesta"],"context_quality":"low","sources":[],"analysis":{},"provider":"gemini:gemini-3.5-flash-lite"}
                """, MediaType.APPLICATION_JSON));

        mockServer.expect(twice(), requestTo("http://ai-engine.test/api/history/s_img?limit=50"))
            .andExpect(method(HttpMethod.GET))
            .andRespond(org.springframework.test.web.client.response.MockRestResponseCreators.withServiceUnavailable());

        String imageChat = """
            {
              "session_id": "s_img",
              "message": "Analiza esta captura",
              "image": {
                "data": "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo=",
                "mime_type": "image/jpeg"
              }
            }
            """;
        mockMvc.perform(post("/api/chat").contentType(MediaType.APPLICATION_JSON).content(imageChat))
            .andExpect(status().isOk());

        mockMvc.perform(get("/api/history/s_img"))
            .andExpect(status().isOk())
            .andExpect(MockMvcResultMatchers.jsonPath("$[0].user_message").value("Analiza esta captura"))
            .andExpect(MockMvcResultMatchers.jsonPath("$[0].user_image_data").value("QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo="))
            .andExpect(MockMvcResultMatchers.jsonPath("$[0].user_image_mime").value("image/jpeg"))
            .andExpect(MockMvcResultMatchers.jsonPath("$[0].bot_response").value("Boleto analizado"));

        mockServer.verify();
    }
}
