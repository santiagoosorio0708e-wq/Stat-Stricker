package com.statstriker.gateway.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "statstriker")
public record GatewayProperties(
    String aiEngineUrl,
    int connectTimeoutMs,
    int readTimeoutMs,
    boolean warmerEnabled,
    long chatCacheTtlSeconds,
    long sessionContextTtlMinutes
) {
    public GatewayProperties {
        if (aiEngineUrl == null || aiEngineUrl.isBlank()) {
            aiEngineUrl = "http://127.0.0.1:8012";
        }
        if (connectTimeoutMs <= 0) {
            connectTimeoutMs = 5000;
        }
        if (readTimeoutMs <= 0) {
            readTimeoutMs = 65000;
        }
        if (chatCacheTtlSeconds <= 0) {
            chatCacheTtlSeconds = 180;
        }
        if (sessionContextTtlMinutes <= 0) {
            sessionContextTtlMinutes = 30;
        }
    }
}
