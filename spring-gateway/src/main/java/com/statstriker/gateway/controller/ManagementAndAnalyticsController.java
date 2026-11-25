package com.statstriker.gateway.controller;

import com.statstriker.gateway.service.ChatAuditAndRatingService;
import com.statstriker.gateway.service.ChatOptimizationService;
import com.statstriker.gateway.service.KnowledgeAndCaseService;
import com.statstriker.gateway.service.SqlAnalyticsService;
import jakarta.validation.Valid;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api")
public class ManagementAndAnalyticsController {

    private final KnowledgeAndCaseService knowledgeService;
    private final SqlAnalyticsService sqlAnalyticsService;
    private final ChatAuditAndRatingService auditService;
    private final ChatOptimizationService chatOptimizationService;

    public ManagementAndAnalyticsController(
        KnowledgeAndCaseService knowledgeService,
        SqlAnalyticsService sqlAnalyticsService,
        ChatAuditAndRatingService auditService,
        ChatOptimizationService chatOptimizationService
    ) {
        this.knowledgeService = knowledgeService;
        this.sqlAnalyticsService = sqlAnalyticsService;
        this.auditService = auditService;
        this.chatOptimizationService = chatOptimizationService;
    }

    @GetMapping("/management/meta")
    public Map<String, Object> meta() {
        return knowledgeService.getMeta();
    }

    @GetMapping("/management/cases")
    public List<KnowledgeAndCaseService.CasoDto> listCases(
        @RequestParam(required = false) Long categoriaId,
        @RequestParam(required = false) String prioridad,
        @RequestParam(required = false) String estado,
        @RequestParam(required = false) String q
    ) {
        return knowledgeService.listCases(categoriaId, prioridad, estado, q);
    }

    @PostMapping("/management/cases")
    @ResponseStatus(HttpStatus.CREATED)
    public KnowledgeAndCaseService.CasoDto createCase(@Valid @RequestBody KnowledgeAndCaseService.CasoRequest request) {
        return knowledgeService.createCase(request);
    }

    @PutMapping("/management/cases/{id}")
    public KnowledgeAndCaseService.CasoDto updateCase(
        @PathVariable Long id,
        @Valid @RequestBody KnowledgeAndCaseService.CasoRequest request
    ) {
        return knowledgeService.updateCase(id, request);
    }

    @DeleteMapping("/management/cases/{id}")
    public Map<String, Boolean> deleteCase(@PathVariable Long id) {
        knowledgeService.deleteCase(id);
        return Map.of("deleted", true);
    }

    @GetMapping("/management/knowledge")
    public List<KnowledgeAndCaseService.ArticuloDto> listKnowledge(
        @RequestParam(required = false) Long categoriaId,
        @RequestParam(required = false) Boolean activo,
        @RequestParam(required = false) String q
    ) {
        return knowledgeService.listArticles(categoriaId, activo, q);
    }

    @PostMapping("/management/knowledge")
    @ResponseStatus(HttpStatus.CREATED)
    public KnowledgeAndCaseService.ArticuloDto createKnowledge(
        @Valid @RequestBody KnowledgeAndCaseService.ArticuloRequest request
    ) {
        KnowledgeAndCaseService.ArticuloDto created = knowledgeService.createArticle(request);
        chatOptimizationService.clearChatCache();
        return created;
    }

    @PutMapping("/management/knowledge/{id}")
    public KnowledgeAndCaseService.ArticuloDto updateKnowledge(
        @PathVariable Long id,
        @Valid @RequestBody KnowledgeAndCaseService.ArticuloRequest request
    ) {
        KnowledgeAndCaseService.ArticuloDto updated = knowledgeService.updateArticle(id, request);
        chatOptimizationService.clearChatCache();
        return updated;
    }

    @PatchMapping("/management/knowledge/{id}/toggle")
    public KnowledgeAndCaseService.ArticuloDto toggleKnowledge(@PathVariable Long id) {
        KnowledgeAndCaseService.ArticuloDto toggled = knowledgeService.toggleArticle(id);
        chatOptimizationService.clearChatCache();
        return toggled;
    }

    @DeleteMapping("/management/knowledge/{id}")
    public Map<String, Boolean> deleteKnowledge(@PathVariable Long id) {
        knowledgeService.deleteArticle(id);
        chatOptimizationService.clearChatCache();
        return Map.of("deleted", true);
    }

    @PostMapping("/chat/ratings")
    public ChatAuditAndRatingService.RatingDto rateResponse(
        @Valid @RequestBody ChatAuditAndRatingService.RatingRequest request
    ) {
        return auditService.saveRating(request);
    }

    @GetMapping("/analytics/sql")
    public Map<String, Object> sqlAnalytics(
        @RequestParam(required = false) String from,
        @RequestParam(required = false) String to,
        @RequestParam(required = false) Long categoriaId,
        @RequestParam(required = false) String prioridad
    ) {
        return sqlAnalyticsService.computeSqlAnalytics(from, to, categoriaId, prioridad);
    }
}
