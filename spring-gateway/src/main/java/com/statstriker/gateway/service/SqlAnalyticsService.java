package com.statstriker.gateway.service;

import java.sql.Timestamp;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

@Service
public class SqlAnalyticsService {

    private final JdbcTemplate jdbcTemplate;

    public SqlAnalyticsService(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public Map<String, Object> computeSqlAnalytics(
        String fromDate,
        String toDate,
        Long categoriaId,
        String prioridad
    ) {
        StringBuilder where = new StringBuilder(" WHERE 1=1 ");
        List<Object> params = new ArrayList<>();

        if (fromDate != null && !fromDate.isBlank()) {
            LocalDate from = LocalDate.parse(fromDate.trim());
            where.append(" AND ac.fecha_creacion >= ? ");
            params.add(Timestamp.valueOf(from.atStartOfDay()));
        }
        if (toDate != null && !toDate.isBlank()) {
            LocalDate to = LocalDate.parse(toDate.trim());
            where.append(" AND ac.fecha_creacion <= ? ");
            params.add(Timestamp.valueOf(to.atTime(23, 59, 59)));
        }
        if (categoriaId != null) {
            where.append(" AND ac.categoria_id = ? ");
            params.add(categoriaId);
        }
        if (prioridad != null && !prioridad.isBlank() && !"ALL".equalsIgnoreCase(prioridad)) {
            where.append(" AND ac.prioridad = ? ");
            params.add(prioridad.trim().toUpperCase(Locale.ROOT));
        }
        Object[] args = params.toArray();

        String summarySql = """
            SELECT
                COUNT(*) AS total_casos,
                COALESCE(SUM(CASE WHEN ac.estado IN ('RESUELTO', 'CERRADO') THEN 1 ELSE 0 END), 0) AS resueltos,
                COALESCE(AVG(CASE
                    WHEN ac.fecha_resolucion IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (ac.fecha_resolucion - ac.fecha_creacion)) / 3600.0
                    ELSE NULL END), 0.0) AS avg_hours
            FROM analisis_casos ac
        """ + where;

        Map<String, Object> summaryRow = jdbcTemplate.queryForMap(summarySql, args);
        long totalCasos = ((Number) summaryRow.get("total_casos")).longValue();
        long resueltos = ((Number) summaryRow.get("resueltos")).longValue();
        double pctResolucion = totalCasos > 0 ? Math.round((1000.0 * resueltos) / totalCasos) / 10.0 : 0.0;
        double avgHours = Math.round(((Number) summaryRow.get("avg_hours")).doubleValue() * 10.0) / 10.0;

        Map<String, Object> iaSummary = jdbcTemplate.queryForMap("""
            SELECT
                (SELECT COUNT(*) FROM consultas_ia) AS total_consultas,
                (SELECT COUNT(*) FROM consultas_ia WHERE estado = 'RESPONDIDA') AS respondidas,
                (SELECT COALESCE(AVG(CAST(puntuacion AS DOUBLE PRECISION)), 0.0) FROM calificaciones) AS avg_rating,
                (SELECT COUNT(*) FROM calificaciones) AS total_ratings,
                (SELECT COUNT(*) FROM articulos_conocimiento WHERE activo = TRUE) AS articulos_activos,
                (SELECT COUNT(*) FROM articulos_conocimiento WHERE activo = FALSE) AS articulos_inactivos
        """);

        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("total_casos", totalCasos);
        summary.put("casos_resueltos", resueltos);
        summary.put("porcentaje_resolucion", pctResolucion);
        summary.put("tiempo_promedio_horas", avgHours);
        summary.put("total_consultas_ia", ((Number) iaSummary.get("total_consultas")).longValue());
        summary.put("consultas_respondidas", ((Number) iaSummary.get("respondidas")).longValue());
        summary.put("calificacion_promedio", Math.round(((Number) iaSummary.get("avg_rating")).doubleValue() * 100.0) / 100.0);
        summary.put("total_calificaciones", ((Number) iaSummary.get("total_ratings")).longValue());
        summary.put("articulos_activos", ((Number) iaSummary.get("articulos_activos")).longValue());
        summary.put("articulos_inactivos", ((Number) iaSummary.get("articulos_inactivos")).longValue());

        String byCategorySql = """
            SELECT c.nombre AS nombre,
                   COUNT(ac.id) AS total,
                   COALESCE(SUM(CASE WHEN ac.estado IN ('RESUELTO', 'CERRADO') THEN 1 ELSE 0 END), 0) AS resueltos
            FROM categorias c
            LEFT JOIN analisis_casos ac ON ac.categoria_id = c.id
        """ + where.toString().replace(" WHERE 1=1 ", " AND 1=1 ") + """
            GROUP BY c.id, c.nombre
            HAVING COUNT(ac.id) > 0
            ORDER BY total DESC, c.nombre ASC
        """;
        List<Map<String, Object>> byCategory = jdbcTemplate.queryForList(byCategorySql, args);
        for (Map<String, Object> row : byCategory) {
            long tot = ((Number) row.get("total")).longValue();
            long res = ((Number) row.get("resueltos")).longValue();
            row.put("pct_resolucion", tot > 0 ? Math.round((1000.0 * res) / tot) / 10.0 : 0.0);
        }

        String byPrioritySql = """
            SELECT ac.prioridad AS prioridad,
                   COUNT(*) AS total,
                   COALESCE(SUM(CASE WHEN ac.estado IN ('RESUELTO', 'CERRADO') THEN 1 ELSE 0 END), 0) AS resueltos
            FROM analisis_casos ac
        """ + where + """
            GROUP BY ac.prioridad
            ORDER BY total DESC
        """;
        List<Map<String, Object>> byPriority = jdbcTemplate.queryForList(byPrioritySql, args);

        String byStatusSql = """
            SELECT ac.estado AS estado, COUNT(*) AS total
            FROM analisis_casos ac
        """ + where + """
            GROUP BY ac.estado
            ORDER BY total DESC
        """;
        List<Map<String, Object>> byStatus = jdbcTemplate.queryForList(byStatusSql, args);

        String weeklySql = """
            SELECT CAST(EXTRACT(YEAR FROM ac.fecha_creacion) AS INTEGER) AS anio,
                   CAST(EXTRACT(WEEK FROM ac.fecha_creacion) AS INTEGER) AS semana_num,
                   COUNT(*) AS total,
                   COALESCE(SUM(CASE WHEN ac.estado IN ('RESUELTO', 'CERRADO') THEN 1 ELSE 0 END), 0) AS resueltos
            FROM analisis_casos ac
        """ + where + """
            GROUP BY CAST(EXTRACT(YEAR FROM ac.fecha_creacion) AS INTEGER),
                     CAST(EXTRACT(WEEK FROM ac.fecha_creacion) AS INTEGER)
            ORDER BY anio ASC, semana_num ASC
        """;
        List<Map<String, Object>> weeklyRaw = jdbcTemplate.queryForList(weeklySql, args);
        List<Map<String, Object>> weeklyTrend = new ArrayList<>();
        for (Map<String, Object> row : weeklyRaw) {
            int yr = ((Number) row.get("anio")).intValue();
            int wk = ((Number) row.get("semana_num")).intValue();
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("semana", String.format("%d-S%02d", yr, wk));
            item.put("total", ((Number) row.get("total")).longValue());
            item.put("resueltos", ((Number) row.get("resueltos")).longValue());
            weeklyTrend.add(item);
        }

        List<Map<String, Object>> iaStatuses = jdbcTemplate.queryForList("""
            SELECT estado, COUNT(*) AS total
            FROM consultas_ia
            GROUP BY estado
            ORDER BY total DESC
        """);

        List<Map<String, Object>> topArticles = jdbcTemplate.queryForList("""
            SELECT COALESCE(ak.titulo, fr.titulo_fuente) AS titulo,
                   COUNT(*) AS usos,
                   COALESCE(AVG(fr.similitud), 0.0) AS similitud_media
            FROM fuentes_respuesta fr
            LEFT JOIN articulos_conocimiento ak ON ak.id = fr.articulo_id
            GROUP BY COALESCE(ak.titulo, fr.titulo_fuente)
            ORDER BY usos DESC
            LIMIT 6
        """);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("summary", summary);
        result.put("by_category", byCategory);
        result.put("by_priority", byPriority);
        result.put("by_status", byStatus);
        result.put("weekly_trend", weeklyTrend);
        result.put("ia_status_distribution", iaStatuses);
        result.put("top_articles", topArticles);
        result.put("generated_at", LocalDateTime.now().toString());
        return result;
    }
}
