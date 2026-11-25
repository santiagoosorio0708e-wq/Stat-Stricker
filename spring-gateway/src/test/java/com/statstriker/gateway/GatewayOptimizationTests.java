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
    "statstriker.ai-engine-url=http://ai-engine.test",
    "spring.datasource.url=jdbc:h2:mem:statstriker_test;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;DB_CLOSE_DELAY=-1",
    "spring.datasource.username=sa",
    "spring.datasource.password="
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

    @Test
    void crudKnowledgeToggleRatingsAndSqlAnalyticsWorkWithoutBreakingChat() throws Exception {
        // 1) Analítica SQL inicial debe reflejar datos sembrados reales
        mockMvc.perform(get("/api/analytics/sql"))
            .andExpect(status().isOk())
            .andExpect(MockMvcResultMatchers.jsonPath("$.summary.total_casos").isNumber())
            .andExpect(MockMvcResultMatchers.jsonPath("$.by_category").isArray())
            .andExpect(MockMvcResultMatchers.jsonPath("$.weekly_trend").isArray());

        // 2) Crear caso CRUD (RF01) y verificar filtro
        String caseBody = """
            {"titulo":"Prueba Liverpool vs Arsenal","descripcion":"Validar mercado BTTS","categoriaId":1,"prioridad":"ALTA","estado":"PENDIENTE","usuarioId":1}
            """;
        String createdCaseJson = mockMvc.perform(post("/api/management/cases")
                .contentType(MediaType.APPLICATION_JSON).content(caseBody))
            .andExpect(status().isCreated())
            .andExpect(MockMvcResultMatchers.jsonPath("$.estado").value("PENDIENTE"))
            .andReturn().getResponse().getContentAsString();
        assertThat(createdCaseJson).contains("Prueba Liverpool vs Arsenal");

        // 3) Crear artículo de conocimiento activo, probar que se inyecta en /api/chat, luego desactivar y verificar que deja de enviarse (RF02)
        String kbBody = """
            {"titulo":"Guia Especial Corners Liverpool","problema":"Analizar corners en Anfield","sintomas":"corners anfield liverpool","causa":"juego por bandas","solucion":"Revisar promedio > 6.5 corners","categoriaId":1,"activo":true,"verificado":true}
            """;
        String kbCreated = mockMvc.perform(post("/api/management/knowledge")
                .contentType(MediaType.APPLICATION_JSON).content(kbBody))
            .andExpect(status().isCreated())
            .andExpect(MockMvcResultMatchers.jsonPath("$.activo").value(true))
            .andReturn().getResponse().getContentAsString();
        Number kbId = com.jayway.jsonpath.JsonPath.read(kbCreated, "$.id");

        mockServer.expect(once(), requestTo("http://ai-engine.test/api/chat"))
            .andExpect(method(HttpMethod.POST))
            .andExpect(MockRestRequestMatchers.jsonPath("$.knowledge_context[0].titulo").value("Guia Especial Corners Liverpool"))
            .andRespond(withSuccess("""
                {"id":55,"answer":"Usando guia de corners","active_rules":["conocimiento_verificado"],"context_quality":"good","sources":[{"id":"kb::1","match":"Guia Especial Corners Liverpool","category":"conocimiento_verificado","similarity":0.9}],"analysis":{},"provider":"gemini:gemini-3.5-flash-lite"}
                """, MediaType.APPLICATION_JSON));

        mockServer.expect(once(), requestTo("http://ai-engine.test/api/chat"))
            .andExpect(method(HttpMethod.POST))
            .andExpect(MockRestRequestMatchers.jsonPath("$.knowledge_context").doesNotExist())
            .andRespond(withSuccess("""
                {"id":56,"answer":"Sin guia desactivada","active_rules":[],"context_quality":"low","sources":[],"analysis":{},"provider":"gemini:gemini-3.5-flash-lite"}
                """, MediaType.APPLICATION_JSON));

        String chatResp = mockMvc.perform(post("/api/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"session_id\":\"s_kb\",\"message\":\"corners anfield liverpool\"}"))
            .andExpect(status().isOk())
            .andExpect(MockMvcResultMatchers.jsonPath("$.respuesta_id").isNumber())
            .andReturn().getResponse().getContentAsString();
        Number respuestaId = com.jayway.jsonpath.JsonPath.read(chatResp, "$.respuesta_id");

        // Calificar respuesta IA (RF08: 1..5)
        mockMvc.perform(post("/api/chat/ratings")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"respuestaId\":" + respuestaId + ",\"puntuacion\":5,\"comentario\":\"Excelente guia\"}"))
            .andExpect(status().isOk())
            .andExpect(MockMvcResultMatchers.jsonPath("$.puntuacion").value(5));

        // Desactivar artículo y comprobar que NO vuelve a enviarse en knowledge_context
        mockMvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch("/api/management/knowledge/" + kbId + "/toggle"))
            .andExpect(status().isOk())
            .andExpect(MockMvcResultMatchers.jsonPath("$.activo").value(false));

        mockMvc.perform(post("/api/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"session_id\":\"s_kb\",\"message\":\"corners anfield liverpool\"}"))
            .andExpect(status().isOk())
            .andExpect(MockMvcResultMatchers.jsonPath("$.answer").value("Sin guia desactivada"));

        mockServer.verify();
    }
}
