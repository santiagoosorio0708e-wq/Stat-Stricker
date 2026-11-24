package com.statstriker.gateway.config;

import com.github.benmanes.caffeine.cache.Caffeine;
import java.net.http.HttpClient;
import java.time.Duration;
import java.util.List;
import org.springframework.cache.CacheManager;
import org.springframework.cache.caffeine.CaffeineCache;
import org.springframework.cache.support.SimpleCacheManager;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class GatewayConfig implements WebMvcConfigurer {

    @Bean
    public RestClient aiEngineRestClient(GatewayProperties props) {
        HttpClient httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .connectTimeout(Duration.ofMillis(props.connectTimeoutMs()))
            .build();
        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory(httpClient);
        requestFactory.setReadTimeout(Duration.ofMillis(props.readTimeoutMs()));

        return RestClient.builder()
            .baseUrl(props.aiEngineUrl())
            .requestFactory(requestFactory)
            .build();
    }

    @Bean
    public CacheManager cacheManager(GatewayProperties props) {
        SimpleCacheManager manager = new SimpleCacheManager();
        manager.setCaches(List.of(
            buildCache("leagues", Duration.ofHours(6), 20),
            buildCache("teams", Duration.ofHours(6), 200),
            buildCache("thesportsdbTeams", Duration.ofHours(6), 50),
            buildCache("analytics", Duration.ofMinutes(10), 10),
            buildCache("matches", Duration.ofMinutes(5), 50),
            buildCache("fixtures", Duration.ofMinutes(2), 200),
            buildCache("fixtureDetails", Duration.ofSeconds(60), 500),
            buildCache("standings", Duration.ofMinutes(3), 100),
            buildCache("teamFixtures", Duration.ofMinutes(3), 300),
            buildCache("teamStatistics", Duration.ofMinutes(5), 300),
            buildCache("live", Duration.ofSeconds(20), 10),
            buildCache("quickAnalysis", Duration.ofMinutes(5), 100),
            buildCache("chatResponses", Duration.ofSeconds(props.chatCacheTtlSeconds()), 300),
            buildAccessCache("sessionMatchContext", Duration.ofMinutes(props.sessionContextTtlMinutes()), 1000),
            buildAccessCache("sessionHistoryBackup", Duration.ofHours(12), 500),
            buildCache("historySessions", Duration.ofMinutes(5), 20)
        ));
        return manager;
    }

    private CaffeineCache buildCache(String name, Duration ttl, long maxSize) {
        return new CaffeineCache(name, Caffeine.newBuilder()
            .expireAfterWrite(ttl)
            .maximumSize(maxSize)
            .recordStats()
            .build());
    }

    private CaffeineCache buildAccessCache(String name, Duration ttl, long maxSize) {
        return new CaffeineCache(name, Caffeine.newBuilder()
            .expireAfterAccess(ttl)
            .maximumSize(maxSize)
            .recordStats()
            .build());
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
            .allowedOrigins("*")
            .allowedMethods("GET", "POST", "DELETE", "OPTIONS")
            .allowedHeaders("*");
    }
}
