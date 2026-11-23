package com.statstriker.gateway.client;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.Optional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

@Component
public class AiEngineClient {

    private static final Logger log = LoggerFactory.getLogger(AiEngineClient.class);

    private final RestClient restClient;

    public AiEngineClient(RestClient aiEngineRestClient) {
        this.restClient = aiEngineRestClient;
    }

    public JsonNode getJson(String pathAndQuery) {
        try {
            return restClient.get()
                .uri(pathAndQuery)
                .accept(MediaType.APPLICATION_JSON)
                .retrieve()
                .body(JsonNode.class);
        } catch (ResourceAccessException | HttpServerErrorException.BadGateway | HttpServerErrorException.ServiceUnavailable | HttpServerErrorException.GatewayTimeout ex) {
            log.debug("Reintentando GET {} tras fallo transitorio: {}", pathAndQuery, ex.getClass().getSimpleName());
            sleepQuietly(250);
            return restClient.get()
                .uri(pathAndQuery)
                .accept(MediaType.APPLICATION_JSON)
                .retrieve()
                .body(JsonNode.class);
        }
    }

    public JsonNode postJson(String path, JsonNode body) {
        return restClient.post()
            .uri(path)
            .contentType(MediaType.APPLICATION_JSON)
            .accept(MediaType.APPLICATION_JSON)
            .body(body)
            .retrieve()
            .body(JsonNode.class);
    }

    public JsonNode deleteJson(String path) {
        return restClient.delete()
            .uri(path)
            .accept(MediaType.APPLICATION_JSON)
            .retrieve()
            .body(JsonNode.class);
    }

    public Optional<JsonNode> checkHealth() {
        try {
            JsonNode node = restClient.get()
                .uri("/api/health")
                .accept(MediaType.APPLICATION_JSON)
                .retrieve()
                .body(JsonNode.class);
            return Optional.ofNullable(node);
        } catch (Exception ex) {
            log.debug("ai-engine health check no disponible: {}", ex.getMessage());
            return Optional.empty();
        }
    }

    private static void sleepQuietly(long millis) {
        try {
            Thread.sleep(millis);
        } catch (InterruptedException ie) {
            Thread.currentThread().interrupt();
        }
    }
}
