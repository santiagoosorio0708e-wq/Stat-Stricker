package com.statstriker.gateway.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.statstriker.gateway.client.AiEngineClient;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.web.util.UriComponentsBuilder;

@Service
public class FootballDataService {

    private final AiEngineClient aiClient;

    public FootballDataService(AiEngineClient aiClient) {
        this.aiClient = aiClient;
    }

    @Cacheable("matches")
    public JsonNode getMatches() {
        return aiClient.getJson("/api/matches");
    }

    @Cacheable("analytics")
    public JsonNode getAnalytics() {
        return aiClient.getJson("/api/analytics");
    }

    @Cacheable(value = "thesportsdbTeams", key = "#leagueId")
    public JsonNode getLeagueTeamsLegacy(String leagueId) {
        String uri = UriComponentsBuilder.fromPath("/api/teams/{leagueId}")
            .buildAndExpand(leagueId)
            .encode()
            .toUriString();
        return aiClient.getJson(uri);
    }

    @Cacheable("leagues")
    public JsonNode getFootballLeagues() {
        return aiClient.getJson("/api/football/leagues");
    }

    @Cacheable("live")
    public JsonNode getFootballLive() {
        return aiClient.getJson("/api/football/live");
    }

    @Cacheable(value = "teams", key = "#league + ':' + #season")
    public JsonNode getFootballTeams(int league, int season) {
        String uri = UriComponentsBuilder.fromPath("/api/football/teams")
            .queryParam("league", league)
            .queryParam("season", season)
            .build()
            .encode()
            .toUriString();
        return aiClient.getJson(uri);
    }

    @Cacheable(value = "standings", key = "#league + ':' + #season")
    public JsonNode getFootballStandings(int league, int season) {
        String uri = UriComponentsBuilder.fromPath("/api/football/standings")
            .queryParam("league", league)
            .queryParam("season", season)
            .build()
            .encode()
            .toUriString();
        return aiClient.getJson(uri);
    }

    @Cacheable(value = "teamFixtures", key = "#teamId + ':' + #season + ':' + #limit")
    public JsonNode getFootballTeamFixtures(int teamId, int season, int limit) {
        String uri = UriComponentsBuilder.fromPath("/api/football/team-fixtures")
            .queryParam("team_id", teamId)
            .queryParam("season", season)
            .queryParam("limit", limit)
            .build()
            .encode()
            .toUriString();
        return aiClient.getJson(uri);
    }

    @Cacheable(value = "teamStatistics", key = "#league + ':' + #season + ':' + #team + ':' + (#teamName == null ? '' : #teamName)")
    public JsonNode getFootballTeamStatistics(int league, int season, int team, String teamName) {
        UriComponentsBuilder builder = UriComponentsBuilder.fromPath("/api/football/team-statistics")
            .queryParam("league", league)
            .queryParam("season", season)
            .queryParam("team", team);
        if (teamName != null && !teamName.isBlank()) {
            builder.queryParam("team_name", teamName);
        }
        return aiClient.getJson(builder.build().encode().toUriString());
    }

    @Cacheable(value = "fixtures", key = "#fromDate + ':' + #toDate + ':' + (#leagues == null ? '' : #leagues)")
    public JsonNode getFootballFixtures(String fromDate, String toDate, String leagues) {
        UriComponentsBuilder builder = UriComponentsBuilder.fromPath("/api/football/fixtures")
            .queryParam("from_date", fromDate)
            .queryParam("to_date", toDate);
        if (leagues != null && !leagues.isBlank()) {
            builder.queryParam("leagues", leagues);
        }
        return aiClient.getJson(builder.build().encode().toUriString());
    }

    @Cacheable(value = "fixtureDetails", key = "#fixtureId")
    public JsonNode getFootballFixtureDetails(int fixtureId) {
        String uri = UriComponentsBuilder.fromPath("/api/football/fixtures/{fixtureId}")
            .buildAndExpand(fixtureId)
            .encode()
            .toUriString();
        return aiClient.getJson(uri);
    }

    @Cacheable(value = "quickAnalysis", key = "#root.target.hashNode(#payload)")
    public JsonNode quickAnalysis(JsonNode payload) {
        return aiClient.postJson("/api/quick-analysis", payload);
    }

    public String hashNode(JsonNode node) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(node.toString().getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hash);
        } catch (NoSuchAlgorithmException ex) {
            return Integer.toHexString(node.toString().hashCode());
        }
    }
}
