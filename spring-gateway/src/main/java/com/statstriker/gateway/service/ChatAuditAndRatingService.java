package com.statstriker.gateway.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.statstriker.gateway.entity.*;
import com.statstriker.gateway.repository.*;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import java.time.LocalDateTime;
import java.util.*;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
public class ChatAuditAndRatingService {

    public record RatingRequest(
        @NotNull Long respuestaId,
        @Min(1) @Max(5) int puntuacion,
        String comentario
    ) {}

    public record RatingDto(Long id, Long respuestaId, int puntuacion, String comentario, LocalDateTime fecha) {}

    public record AuditResult(Long consultaId, Long respuestaId, String consultaEstado) {}

    private final ConsultaIARepository consultaRepo;
    private final RespuestaIARepository respuestaRepo;
    private final FuenteRespuestaRepository fuenteRepo;
    private final CalificacionRepository calificacionRepo;
    private final ArticuloConocimientoRepository articuloRepo;
    private final UsuarioRepository usuarioRepo;

    public ChatAuditAndRatingService(
        ConsultaIARepository consultaRepo,
        RespuestaIARepository respuestaRepo,
        FuenteRespuestaRepository fuenteRepo,
        CalificacionRepository calificacionRepo,
        ArticuloConocimientoRepository articuloRepo,
        UsuarioRepository usuarioRepo
    ) {
        this.consultaRepo = consultaRepo;
        this.respuestaRepo = respuestaRepo;
        this.fuenteRepo = fuenteRepo;
        this.calificacionRepo = calificacionRepo;
        this.articuloRepo = articuloRepo;
        this.usuarioRepo = usuarioRepo;
    }

    @Transactional
    public AuditResult recordChatInteraction(String sessionId, String pregunta, JsonNode response) {
        ConsultaIA consulta = new ConsultaIA();
        consulta.setSessionId(sessionId != null && !sessionId.isBlank() ? sessionId : "default");
        consulta.setPregunta(pregunta != null && !pregunta.isBlank() ? pregunta : "📸 Foto de apuesta adjunta");
        String contextQuality = response.hasNonNull("context_quality") ? response.get("context_quality").asText("none") : "none";
        String estado = "none".equalsIgnoreCase(contextQuality) ? "SIN_RESULTADOS" : "RESPONDIDA";
        consulta.setEstado(estado);
        usuarioRepo.findAll().stream().findFirst().ifPresent(consulta::setUsuario);
        consulta = consultaRepo.save(consulta);

        RespuestaIA resp = new RespuestaIA();
        resp.setConsulta(consulta);
        resp.setRespuesta(response.hasNonNull("answer") ? response.get("answer").asText("") : "");
        resp.setModelo(response.hasNonNull("provider") ? response.get("provider").asText("gemini") : "gemini");
        resp = respuestaRepo.save(resp);

        JsonNode sourcesNode = response.get("sources");
        if (sourcesNode != null && sourcesNode.isArray()) {
            for (JsonNode src : sourcesNode) {
                FuenteRespuesta fuente = new FuenteRespuesta();
                fuente.setRespuesta(resp);
                String srcId = src.hasNonNull("id") ? src.get("id").asText("") : "";
                if (srcId.startsWith("kb::")) {
                    try {
                        Long artId = Long.parseLong(srcId.substring(4));
                        articuloRepo.findById(artId).ifPresent(fuente::setArticulo);
                    } catch (NumberFormatException ignored) {}
                }
                String title = src.hasNonNull("match") ? src.get("match").asText("Fuente") : "Fuente";
                fuente.setTituloFuente(title.length() > 220 ? title.substring(0, 220) : title);
                fuente.setCategoria(src.hasNonNull("category") ? src.get("category").asText("rag") : "rag");
                fuente.setSimilitud(src.hasNonNull("similarity") ? src.get("similarity").asDouble(0.0) : 0.0);
                fuenteRepo.save(fuente);
            }
        }
        return new AuditResult(consulta.getId(), resp.getId(), estado);
    }

    @Transactional
    public void recordErrorInteraction(String sessionId, String pregunta) {
        ConsultaIA consulta = new ConsultaIA();
        consulta.setSessionId(sessionId != null && !sessionId.isBlank() ? sessionId : "default");
        consulta.setPregunta(pregunta != null && !pregunta.isBlank() ? pregunta : "Consulta sin texto");
        consulta.setEstado("ERROR");
        usuarioRepo.findAll().stream().findFirst().ifPresent(consulta::setUsuario);
        consultaRepo.save(consulta);
    }

    @Transactional
    public RatingDto saveRating(RatingRequest req) {
        RespuestaIA resp = respuestaRepo.findById(req.respuestaId())
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Respuesta IA no encontrada."));
        Calificacion cal = calificacionRepo.findByRespuestaId(resp.getId()).orElseGet(Calificacion::new);
        cal.setRespuesta(resp);
        cal.setPuntuacion(req.puntuacion());
        cal.setComentario(req.comentario() != null ? req.comentario().trim() : "");
        cal.setFecha(LocalDateTime.now());
        cal = calificacionRepo.save(cal);
        return new RatingDto(cal.getId(), resp.getId(), cal.getPuntuacion(), cal.getComentario(), cal.getFecha());
    }

    @Transactional(readOnly = true)
    public void enrichHistoryWithJpaMetadata(String sessionId, JsonNode historyArray) {
        if (historyArray == null || !historyArray.isArray() || historyArray.isEmpty()) {
            return;
        }
        List<ConsultaIA> consultas = consultaRepo.findBySessionIdOrderByFechaAsc(sessionId);
        if (consultas.isEmpty()) {
            return;
        }
        Map<String, RespuestaIA> byQuestion = new HashMap<>();
        for (ConsultaIA c : consultas) {
            respuestaRepo.findByConsultaId(c.getId()).ifPresent(r -> byQuestion.put(c.getPregunta(), r));
        }
        for (JsonNode row : historyArray) {
            if (!row.isObject()) continue;
            ObjectNode obj = (ObjectNode) row;
            String userMsg = obj.hasNonNull("user_message") ? obj.get("user_message").asText("") : "";
            RespuestaIA matchResp = byQuestion.get(userMsg);
            if (matchResp != null) {
                obj.put("respuesta_id", matchResp.getId());
                calificacionRepo.findByRespuestaId(matchResp.getId()).ifPresent(cal -> {
                    obj.put("calificacion", cal.getPuntuacion());
                    obj.put("calificacion_comentario", cal.getComentario());
                });
            }
        }
    }
}
