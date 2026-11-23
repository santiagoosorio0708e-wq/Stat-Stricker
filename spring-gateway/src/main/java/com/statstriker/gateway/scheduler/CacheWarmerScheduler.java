package com.statstriker.gateway.scheduler;

import com.statstriker.gateway.client.AiEngineClient;
import com.statstriker.gateway.config.GatewayProperties;
import com.statstriker.gateway.service.FootballDataService;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.concurrent.Executors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class CacheWarmerScheduler {

    private static final Logger log = LoggerFactory.getLogger(CacheWarmerScheduler.class);
    private static final ZoneId BOGOTA_ZONE = ZoneId.of("America/Bogota");

    private final GatewayProperties props;
    private final AiEngineClient aiClient;
    private final FootballDataService footballService;

    public CacheWarmerScheduler(
        GatewayProperties props,
        AiEngineClient aiClient,
        FootballDataService footballService
    ) {
        this.props = props;
        this.aiClient = aiClient;
        this.footballService = footballService;
    }

    @Scheduled(initialDelay = 12_000, fixedDelay = 180_000)
    public void warmCaches() {
        if (!props.warmerEnabled() || aiClient.checkHealth().isEmpty()) {
            return;
        }
        String today = LocalDate.now(BOGOTA_ZONE).toString();
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            executor.submit(() -> runQuietly("leagues", footballService::getFootballLeagues));
            executor.submit(() -> runQuietly("matches", footballService::getMatches));
            executor.submit(() -> runQuietly("live", footballService::getFootballLive));
            executor.submit(() -> runQuietly("fixtures", () -> footballService.getFootballFixtures(today, today, "")));
        }
        log.debug("Precalentamiento de caché completado para {}", today);
    }

    private void runQuietly(String label, Runnable task) {
        try {
            task.run();
        } catch (Exception ex) {
            log.debug("No se pudo precalentar '{}': {}", label, ex.getMessage());
        }
    }
}
