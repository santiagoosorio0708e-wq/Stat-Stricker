package com.statstriker.gateway.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.github.benmanes.caffeine.cache.stats.CacheStats;
import com.statstriker.gateway.client.AiEngineClient;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.text.Normalizer;
import java.time.Instant;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;
import java.util.regex.Pattern;
import org.springframework.cache.Cache;
import org.springframework.cache.CacheManager;
import org.springframework.cache.caffeine.CaffeineCache;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.ResourceAccessException;

@Service
public class ChatOptimizationService {

    private static final Pattern NEW_MATCHUP_PATTERN = Pattern.compile("\\b(vs|contra)\\b", Pattern.CASE_INSENSITIVE);
    private static final Pattern MULTI_SPACE = Pattern.compile("\\s+");

    private final AiEngineClient aiClient;
    private final CacheManager cacheManager;
    private final ObjectMapper objectMapper;

    private final AtomicLong chatCacheHits = new AtomicLong();
    private final AtomicLong chatCacheMisses = new AtomicLong();
    private final AtomicLong enrichedFollowUps = new AtomicLong();
    private final AtomicLong totalAiCalls = new AtomicLong();
    private final AtomicLong totalAiLatencyMs = new AtomicLong();

    public ChatOptimizationService(AiEngineClient aiClient, CacheManager cacheManager, ObjectMapper objectMapper) {
        this.aiClient = aiClient;
        this.cacheManager = cacheManager;
        this.objectMapper = objectMapper;
    }

    public JsonNode processChat(JsonNode requestBody) {
        ObjectNode payload = requestBody.isObject()
            ? ((ObjectNode) requestBody).deepCopy()
            : null;
        if (payload == null) {
            return aiClient.postJson("/api/chat", requestBody);
        }

        String sessionId = textOrDefault(payload.get("session_id"), "default");
        String message = textOrDefault(payload.get("message"), "");
        JsonNode imageNode = payload.get("image");
        boolean hasImage = imageNode != null && !imageNode.isNull() && imageNode.isObject();

        Cache sessionCache = cacheManager.getCache("sessionMatchContext");
        JsonNode matchContext = payload.get("match_context");
        if (matchContext != null && !matchContext.isNull() && matchContext.isObject()) {
            if (sessionCache != null) {
                sessionCache.put(sessionId, matchContext.deepCopy());
            }
        } else if (sessionCache != null && !NEW_MATCHUP_PATTERN.matcher(message).find()) {
            JsonNode remembered = sessionCache.get(sessionId, JsonNode.class);
            if (remembered != null && remembered.isObject()) {
                payload.set("match_context", remembered.deepCopy());
                enrichedFollowUps.incrementAndGet();
            }
        }

        String cacheKey = hasImage ? null : buildChatCacheKey(sessionId, message, payload.get("match_context"));
        Cache chatCache = cacheManager.getCache("chatResponses");
        if (cacheKey != null && chatCache != null) {
            JsonNode cached = chatCache.get(cacheKey, JsonNode.class);
            if (cached != null) {
                chatCacheHits.incrementAndGet();
                return cached.deepCopy();
            }
        }

        chatCacheMisses.incrementAndGet();
        long startNs = System.nanoTime();
        JsonNode response = aiClient.postJson("/api/chat", payload);
        long elapsedMs = (System.nanoTime() - startNs) / 1_000_000L;
        totalAiCalls.incrementAndGet();
        totalAiLatencyMs.addAndGet(elapsedMs);

        if (response != null && response.isObject()) {
            appendHistoryBackup(sessionId, message, imageNode, response);
            if (cacheKey != null && chatCache != null) {
                String provider = textOrDefault(response.get("provider"), "");
                if (!"local-fallback".equals(provider)) {
                    chatCache.put(cacheKey, response.deepCopy());
                }
            }
        }
        return response;
    }

    public JsonNode getHistoryWithFallback(String sessionId, String historyUri) {
        Cache backupCache = cacheManager.getCache("sessionHistoryBackup");
        try {
            JsonNode liveHistory = aiClient.getJson(historyUri);
            if (liveHistory != null && liveHistory.isArray() && backupCache != null) {
                backupCache.put(sessionId, liveHistory.deepCopy());
            }
            return liveHistory;
        } catch (ResourceAccessException | HttpServerErrorException ex) {
            if (backupCache != null) {
                JsonNode cached = backupCache.get(sessionId, JsonNode.class);
                if (cached != null && cached.isArray()) {
                    return cached.deepCopy();
                }
            }
            return objectMapper.createArrayNode();
        }
    }

    public JsonNode listSessionsWithFallback(String sessionsUri) {
        Cache sessionsCache = cacheManager.getCache("historySessions");
        try {
            JsonNode liveSessions = aiClient.getJson(sessionsUri);
            if (liveSessions != null && liveSessions.isArray() && sessionsCache != null) {
                sessionsCache.put("all", liveSessions.deepCopy());
            }
            return liveSessions;
        } catch (ResourceAccessException | HttpServerErrorException ex) {
            if (sessionsCache != null) {
                JsonNode cached = sessionsCache.get("all", JsonNode.class);
                if (cached != null && cached.isArray()) {
                    return cached.deepCopy();
                }
            }
            return objectMapper.createArrayNode();
        }
    }

    public void invalidateSession(String sessionId) {
        Cache sessionCache = cacheManager.getCache("sessionMatchContext");
        if (sessionCache != null) {
            sessionCache.evict(sessionId);
        }
        Cache backupCache = cacheManager.getCache("sessionHistoryBackup");
        if (backupCache != null) {
            backupCache.evict(sessionId);
        }
        Cache sessionsCache = cacheManager.getCache("historySessions");
        if (sessionsCache != null) {
            sessionsCache.clear();
        }
        Cache chatCache = cacheManager.getCache("chatResponses");
        if (chatCache instanceof CaffeineCache caffeineCache) {
            String prefix = sessionId + ":";
            caffeineCache.getNativeCache().asMap().keySet().removeIf(k -> k.toString().startsWith(prefix));
        }
    }

    private void appendHistoryBackup(String sessionId, String userMessage, JsonNode imageNode, JsonNode response) {
        Cache backupCache = cacheManager.getCache("sessionHistoryBackup");
        if (backupCache == null) {
            return;
        }
        JsonNode existing = backupCache.get(sessionId, JsonNode.class);
        ArrayNode turns = (existing != null && existing.isArray())
            ? ((ArrayNode) existing).deepCopy()
            : objectMapper.createArrayNode();

        ObjectNode turn = objectMapper.createObjectNode();
        turn.put("id", response.hasNonNull("id") ? response.get("id").asLong() : turns.size() + 1L);
        String storedUser = userMessage.isBlank() ? "📸 Foto de apuesta adjunta" : userMessage;
        turn.put("user_message", storedUser);
        turn.put("user_image_data", imageNode != null && imageNode.hasNonNull("data") ? imageNode.get("data").asText("") : "");
        turn.put("user_image_mime", imageNode != null && imageNode.hasNonNull("mime_type") ? imageNode.get("mime_type").asText("") : "");
        turn.put("bot_response", textOrDefault(response.get("answer"), ""));
        turn.set("active_rules", response.has("active_rules") ? response.get("active_rules").deepCopy() : objectMapper.createArrayNode());
        turn.set("sources", response.has("sources") ? response.get("sources").deepCopy() : objectMapper.createArrayNode());
        turn.put("provider", textOrDefault(response.get("provider"), ""));
        turn.put("created_at", Instant.now().toString());

        turns.add(turn);
        backupCache.put(sessionId, turns);
        Cache sessionsCache = cacheManager.getCache("historySessions");
        if (sessionsCache != null) {
            sessionsCache.clear();
        }
    }

    public Map<String, Object> metricsSnapshot() {
        long calls = totalAiCalls.get();
        long avgLatencyMs = calls > 0 ? totalAiLatencyMs.get() / calls : 0L;

        long footballHits = 0L;
        long footballRequests = 0L;
        for (String name : cacheManager.getCacheNames()) {
            if ("chatResponses".equals(name)
                || "sessionMatchContext".equals(name)
                || "sessionHistoryBackup".equals(name)
                || "historySessions".equals(name)) {
                continue;
            }
            Cache cache = cacheManager.getCache(name);
            if (cache instanceof CaffeineCache caffeineCache) {
                CacheStats stats = caffeineCache.getNativeCache().stats();
                footballHits += stats.hitCount();
                footballRequests += stats.requestCount();
            }
        }

        Map<String, Object> metrics = new LinkedHashMap<>();
        metrics.put("engine", "spring-boot");
        metrics.put("java", Runtime.version().feature());
        metrics.put("virtual_threads", true);
        metrics.put("chat_cache_hits", chatCacheHits.get());
        metrics.put("chat_cache_misses", chatCacheMisses.get());
        metrics.put("enriched_followups", enrichedFollowUps.get());
        metrics.put("ai_calls", calls);
        metrics.put("avg_ai_latency_ms", avgLatencyMs);
        metrics.put("football_cache_hits", footballHits);
        metrics.put("football_cache_requests", footballRequests);
        return metrics;
    }

    private String buildChatCacheKey(String sessionId, String message, JsonNode matchContext) {
        String normalizedMsg = MULTI_SPACE.matcher(
            Normalizer.normalize(message.trim().toLowerCase(Locale.ROOT), Normalizer.Form.NFD)
                .replaceAll("\\p{M}+", "")
        ).replaceAll(" ");
        if (normalizedMsg.isEmpty()) {
            return null;
        }
        String matchId = matchContext != null && matchContext.hasNonNull("id")
            ? matchContext.get("id").asText("")
            : "";
        return sessionId + ":" + sha256(normalizedMsg + "|" + matchId);
    }

    private static String textOrDefault(JsonNode node, String fallback) {
        return node != null && !node.isNull() ? node.asText(fallback) : fallback;
    }

    private static String sha256(String input) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(input.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException ex) {
            return Integer.toHexString(input.hashCode());
        }
    }
}
