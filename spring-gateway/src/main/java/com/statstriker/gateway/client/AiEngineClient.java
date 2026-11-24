package com.statstriker.gateway.client;

import com.fasterxml.jackson.databind.JsonNode;
import com.statstriker.gateway.config.GatewayProperties;
import java.net.URI;
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
    private final String baseUrl;

    public AiEngineClient(RestClient aiEngineRestClient, GatewayProperties props) {
        this.restClient = aiEngineRestClient;
        String url = props.aiEngineUrl() != null ? props.aiEngineUrl().trim() : "http://127.0.0.1:8012";
        this.baseUrl = url.endsWith("/") ? url.substring(0, url.length() - 1) : url;
    }

    public JsonNode getJson(String pathAndQuery) {
        URI targetUri = URI.create(baseUrl + pathAndQuery);
        try {
            return restClient.get()
                .uri(targetUri)
                .accept(MediaType.APPLICATION_JSON)
                .retrieve()
                .body(JsonNode.class);
        } catch (ResourceAccessException | HttpServerErrorException.BadGateway | HttpServerErrorException.ServiceUnavailable | HttpServerErrorException.GatewayTimeout ex) {
            log.debug("Reintentando GET {} tras fallo transitorio: {}", pathAndQuery, ex.getClass().getSimpleName());
            sleepQuietly(250);
            return restClient.get()
                .uri(targetUri)
                .accept(MediaType.APPLICATION_JSON)
                .retrieve()
                .body(JsonNode.class);
        }
    }

    public JsonNode postJson(String path, JsonNode body) {
        return restClient.post()
            .uri(URI.create(baseUrl + path))
            .contentType(MediaType.APPLICATION_JSON)
            .accept(MediaType.APPLICATION_JSON)
            .body(body)
            .retrieve()
            .body(JsonNode.class);
    }

    public JsonNode deleteJson(String path) {
        return restClient.delete()
            .uri(URI.create(baseUrl + path))
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
