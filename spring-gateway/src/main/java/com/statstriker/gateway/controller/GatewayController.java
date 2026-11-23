package com.statstriker.gateway.controller;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.statstriker.gateway.client.AiEngineClient;
import com.statstriker.gateway.service.ChatOptimizationService;
import com.statstriker.gateway.service.FootballDataService;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.util.UriComponentsBuilder;

@RestController
@RequestMapping("/api")
public class GatewayController {

    private final AiEngineClient aiClient;
    private final FootballDataService footballService;
    private final ChatOptimizationService chatService;
    private final ObjectMapper objectMapper;

    public GatewayController(
        AiEngineClient aiClient,
        FootballDataService footballService,
        ChatOptimizationService chatService,
        ObjectMapper objectMapper
    ) {
        this.aiClient = aiClient;
        this.footballService = footballService;
        this.chatService = chatService;
        this.objectMapper = objectMapper;
    }

    @GetMapping("/health")
    public JsonNode health() {
        ObjectNode gatewayNode = objectMapper.valueToTree(chatService.metricsSnapshot());
        return aiClient.checkHealth()
            .map(node -> {
                ObjectNode copy = node.isObject() ? ((ObjectNode) node).deepCopy() : objectMapper.createObjectNode();
                copy.set("gateway", gatewayNode);
                return (JsonNode) copy;
            })
            .orElseGet(() -> {
                ObjectNode degraded = objectMapper.createObjectNode();
                degraded.put("status", "degraded");
                degraded.set("llm", objectMapper.createObjectNode()
                    .put("ready", false)
                    .put("error", "El motor Python RAG está iniciándose o desconectado."));
                degraded.set("vector_db", objectMapper.createObjectNode().put("engine", "chromadb").put("documents", 0));
                degraded.set("history_storage", objectMapper.createObjectNode().put("engine", "SQLite").put("persistent", true));
                degraded.set("gateway", gatewayNode);
                return degraded;
            });
    }

    @GetMapping("/gateway/metrics")
    public Map<String, Object> gatewayMetrics() {
        Map<String, Object> metrics = new LinkedHashMap<>(chatService.metricsSnapshot());
        metrics.put("ai_engine_up", aiClient.checkHealth().isPresent());
        return metrics;
    }

    @GetMapping("/matches")
    public JsonNode matches() {
        return footballService.getMatches();
    }

    @GetMapping("/analytics")
    public JsonNode analytics() {
        return footballService.getAnalytics();
    }

    @GetMapping("/teams/{leagueId}")
    public JsonNode legacyTeams(@PathVariable String leagueId) {
        return footballService.getLeagueTeamsLegacy(leagueId);
    }

    @GetMapping("/football/leagues")
    public JsonNode footballLeagues() {
        return footballService.getFootballLeagues();
    }

    @GetMapping("/football/live")
    public JsonNode footballLive() {
        return footballService.getFootballLive();
    }

    @GetMapping("/football/teams")
    public JsonNode footballTeams(@RequestParam int league, @RequestParam int season) {
        return footballService.getFootballTeams(league, season);
    }

    @GetMapping("/football/standings")
    public JsonNode footballStandings(@RequestParam int league, @RequestParam int season) {
        return footballService.getFootballStandings(league, season);
    }

    @GetMapping("/football/team-fixtures")
    public JsonNode footballTeamFixtures(
        @RequestParam("team_id") int teamId,
        @RequestParam int season,
        @RequestParam(defaultValue = "10") int limit
    ) {
        return footballService.getFootballTeamFixtures(teamId, season, limit);
    }

    @GetMapping("/football/team-statistics")
    public JsonNode footballTeamStatistics(
        @RequestParam int league,
        @RequestParam int season,
        @RequestParam int team,
        @RequestParam(value = "team_name", defaultValue = "") String teamName
    ) {
        return footballService.getFootballTeamStatistics(league, season, team, teamName);
    }

    @GetMapping("/football/fixtures")
    public JsonNode footballFixtures(
        @RequestParam("from_date") String fromDate,
        @RequestParam("to_date") String toDate,
        @RequestParam(defaultValue = "") String leagues
    ) {
        return footballService.getFootballFixtures(fromDate, toDate, leagues);
    }

    @GetMapping("/football/fixtures/{fixtureId}")
    public JsonNode footballFixtureDetails(@PathVariable int fixtureId) {
        return footballService.getFootballFixtureDetails(fixtureId);
    }

    @PostMapping("/quick-analysis")
    public JsonNode quickAnalysis(@RequestBody JsonNode payload) {
        return footballService.quickAnalysis(payload);
    }

    @PostMapping("/chat")
    public JsonNode chat(@RequestBody JsonNode payload) {
        return chatService.processChat(payload);
    }

    @GetMapping("/history/{sessionId}")
    public JsonNode history(
        @PathVariable String sessionId,
        @RequestParam(defaultValue = "50") int limit
    ) {
        String uri = UriComponentsBuilder.fromPath("/api/history/{sessionId}")
            .queryParam("limit", limit)
            .buildAndExpand(sessionId)
            .encode()
            .toUriString();
        return aiClient.getJson(uri);
    }

    @DeleteMapping("/history/{sessionId}")
    public JsonNode deleteHistory(@PathVariable String sessionId) {
        chatService.invalidateSession(sessionId);
        String uri = UriComponentsBuilder.fromPath("/api/history/{sessionId}")
            .buildAndExpand(sessionId)
            .encode()
            .toUriString();
        return aiClient.deleteJson(uri);
    }
}
