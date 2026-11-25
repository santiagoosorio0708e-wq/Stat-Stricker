package com.statstriker.gateway.service;

import com.statstriker.gateway.entity.AnalisisCaso;
import com.statstriker.gateway.entity.ArticuloConocimiento;
import com.statstriker.gateway.entity.Categoria;
import com.statstriker.gateway.entity.Usuario;
import com.statstriker.gateway.repository.AnalisisCasoRepository;
import com.statstriker.gateway.repository.ArticuloConocimientoRepository;
import com.statstriker.gateway.repository.CategoriaRepository;
import com.statstriker.gateway.repository.ConsultaIARepository;
import com.statstriker.gateway.repository.FuenteRespuestaRepository;
import com.statstriker.gateway.repository.UsuarioRepository;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.text.Normalizer;
import java.time.LocalDateTime;
import java.util.*;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
public class KnowledgeAndCaseService {

    private static final Set<String> STOPWORDS = Set.of(
        "el", "la", "los", "las", "un", "una", "de", "del", "al", "en", "con", "para", "por",
        "que", "si", "como", "cual", "sobre", "entre", "contra", "vs", "y", "o", "es", "son"
    );

    public record CategoriaDto(Long id, String nombre, String descripcion, String ligaCodigo) {}
    public record UsuarioDto(Long id, String nombre, String correo, String area) {}
    public record CasoDto(
        Long id, String titulo, String descripcion,
        Long categoriaId, String categoriaNombre,
        String prioridad, String estado,
        LocalDateTime fechaCreacion, LocalDateTime fechaResolucion,
        Long usuarioId, String usuarioNombre
    ) {}
    public record ArticuloDto(
        Long id, String titulo, String problema, String sintomas, String causa, String solucion,
        Long categoriaId, String categoriaNombre,
        boolean activo, boolean verificado,
        LocalDateTime fechaCreacion, LocalDateTime fechaActualizacion
    ) {}
    public record CasoRequest(
        @NotBlank String titulo,
        @NotBlank String descripcion,
        @NotNull Long categoriaId,
        @NotBlank String prioridad,
        @NotBlank String estado,
        Long usuarioId
    ) {}
    public record ArticuloRequest(
        @NotBlank String titulo,
        @NotBlank String problema,
        @NotBlank String sintomas,
        @NotBlank String causa,
        @NotBlank String solucion,
        @NotNull Long categoriaId,
        Boolean activo,
        Boolean verificado
    ) {}

    private final AnalisisCasoRepository casoRepo;
    private final ArticuloConocimientoRepository articuloRepo;
    private final CategoriaRepository categoriaRepo;
    private final UsuarioRepository usuarioRepo;
    private final ConsultaIARepository consultaRepo;
    private final FuenteRespuestaRepository fuenteRepo;

    public KnowledgeAndCaseService(
        AnalisisCasoRepository casoRepo,
        ArticuloConocimientoRepository articuloRepo,
        CategoriaRepository categoriaRepo,
        UsuarioRepository usuarioRepo,
        ConsultaIARepository consultaRepo,
        FuenteRespuestaRepository fuenteRepo
    ) {
        this.casoRepo = casoRepo;
        this.articuloRepo = articuloRepo;
        this.categoriaRepo = categoriaRepo;
        this.usuarioRepo = usuarioRepo;
        this.consultaRepo = consultaRepo;
        this.fuenteRepo = fuenteRepo;
    }

    @Transactional(readOnly = true)
    public Map<String, Object> getMeta() {
        List<CategoriaDto> categories = categoriaRepo.findAll().stream()
            .sorted(Comparator.comparing(Categoria::getId))
            .map(c -> new CategoriaDto(c.getId(), c.getNombre(), c.getDescripcion(), c.getLigaCodigo()))
            .toList();
        List<UsuarioDto> users = usuarioRepo.findAll().stream()
            .sorted(Comparator.comparing(Usuario::getId))
            .map(u -> new UsuarioDto(u.getId(), u.getNombre(), u.getCorreo(), u.getArea()))
            .toList();
        return Map.of("categories", categories, "users", users);
    }

    @Transactional(readOnly = true)
    public List<CasoDto> listCases(Long categoriaId, String prioridad, String estado, String q) {
        return casoRepo.searchFiltered(
            categoriaId,
            normalizeFilter(prioridad),
            normalizeFilter(estado),
            normalizeSearch(q)
        ).stream().map(this::toCasoDto).toList();
    }

    @Transactional
    public CasoDto createCase(CasoRequest req) {
        AnalisisCaso caso = new AnalisisCaso();
        applyCaseFields(caso, req);
        return toCasoDto(casoRepo.save(caso));
    }

    @Transactional
    public CasoDto updateCase(Long id, CasoRequest req) {
        AnalisisCaso caso = casoRepo.findById(id)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Caso no encontrado."));
        applyCaseFields(caso, req);
        return toCasoDto(casoRepo.save(caso));
    }

    @Transactional
    public void deleteCase(Long id) {
        if (!casoRepo.existsById(id)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Caso no encontrado.");
        }
        if (consultaRepo.existsByAnalisisCasoId(id)) {
            throw new ResponseStatusException(
                HttpStatus.CONFLICT,
                "No se puede eliminar porque el caso tiene consultas IA asociadas; cambia su estado a CERRADO."
            );
        }
        casoRepo.deleteById(id);
    }

    @Transactional(readOnly = true)
    public List<ArticuloDto> listArticles(Long categoriaId, Boolean activo, String q) {
        return articuloRepo.searchFiltered(categoriaId, activo, normalizeSearch(q))
            .stream().map(this::toArticuloDto).toList();
    }

    @Transactional
    public ArticuloDto createArticle(ArticuloRequest req) {
        ArticuloConocimiento art = new ArticuloConocimiento();
        applyArticleFields(art, req);
        return toArticuloDto(articuloRepo.save(art));
    }

    @Transactional
    public ArticuloDto updateArticle(Long id, ArticuloRequest req) {
        ArticuloConocimiento art = articuloRepo.findById(id)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Artículo no encontrado."));
        applyArticleFields(art, req);
        return toArticuloDto(articuloRepo.save(art));
    }

    @Transactional
    public ArticuloDto toggleArticle(Long id) {
        ArticuloConocimiento art = articuloRepo.findById(id)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Artículo no encontrado."));
        art.setActivo(!art.isActivo());
        if (art.isActivo()) {
            art.setVerificado(true);
        }
        return toArticuloDto(articuloRepo.save(art));
    }

    @Transactional
    public void deleteArticle(Long id) {
        if (!articuloRepo.existsById(id)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Artículo no encontrado.");
        }
        if (fuenteRepo.existsByArticuloId(id)) {
            throw new ResponseStatusException(
                HttpStatus.CONFLICT,
                "No se puede eliminar porque el artículo ya fue citado en auditoría IA; usa Desactivar para excluirlo sin perder trazabilidad."
            );
        }
        articuloRepo.deleteById(id);
    }

    @Transactional(readOnly = true)
    public List<Map<String, Object>> findRelevantActiveKnowledge(String queryText) {
        Set<String> queryTokens = tokenize(queryText);
        if (queryTokens.isEmpty()) {
            return List.of();
        }
        List<ArticuloConocimiento> active = articuloRepo.findAllActiveAndVerified();
        List<Map<String, Object>> scored = new ArrayList<>();
        for (ArticuloConocimiento art : active) {
            String fullText = art.getTitulo() + " " + art.getProblema() + " " + art.getSintomas()
                + " " + art.getCausa() + " " + art.getSolucion() + " " + art.getCategoria().getNombre();
            Set<String> docTokens = tokenize(fullText);
            long overlap = queryTokens.stream().filter(docTokens::contains).count();
            if (overlap == 0) {
                continue;
            }
            double sim = Math.min(0.95, 0.60 + 0.12 * overlap);
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", art.getId());
            item.put("titulo", art.getTitulo());
            item.put("problema", art.getProblema());
            item.put("sintomas", art.getSintomas());
            item.put("causa", art.getCausa());
            item.put("solucion", art.getSolucion());
            item.put("categoria", art.getCategoria().getNombre());
            item.put("similarity", Math.round(sim * 1000.0) / 1000.0);
            scored.add(item);
        }
        scored.sort((a, b) -> Double.compare((Double) b.get("similarity"), (Double) a.get("similarity")));
        return scored.size() > 3 ? scored.subList(0, 3) : scored;
    }

    @Transactional(readOnly = true)
    public long activeKnowledgeVersionHash() {
        return articuloRepo.findAllActiveAndVerified().stream()
            .mapToLong(a -> Objects.hash(a.getId(), a.isActivo(), a.isVerificado(), a.getFechaActualizacion()))
            .reduce(17L, (acc, h) -> acc * 31L + h);
    }

    private void applyCaseFields(AnalisisCaso caso, CasoRequest req) {
        Categoria cat = categoriaRepo.findById(req.categoriaId())
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "Categoría no válida."));
        Usuario user = req.usuarioId() != null
            ? usuarioRepo.findById(req.usuarioId()).orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "Usuario no válido."))
            : usuarioRepo.findAll().stream().findFirst().orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "No hay usuarios registrados."));

        String prioridad = validateEnum(req.prioridad(), Set.of("ALTA", "MEDIA", "BAJA"), "prioridad");
        String estado = validateEnum(req.estado(), Set.of("PENDIENTE", "EN_ANALISIS", "RESUELTO", "CERRADO"), "estado");

        caso.setTitulo(req.titulo().trim());
        caso.setDescripcion(req.descripcion().trim());
        caso.setCategoria(cat);
        caso.setPrioridad(prioridad);
        caso.setEstado(estado);
        caso.setUsuario(user);
        if ("RESUELTO".equals(estado) || "CERRADO".equals(estado)) {
            if (caso.getFechaResolucion() == null) {
                caso.setFechaResolucion(LocalDateTime.now());
            }
        } else {
            caso.setFechaResolucion(null);
        }
    }

    private void applyArticleFields(ArticuloConocimiento art, ArticuloRequest req) {
        Categoria cat = categoriaRepo.findById(req.categoriaId())
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "Categoría no válida."));
        art.setTitulo(req.titulo().trim());
        art.setProblema(req.problema().trim());
        art.setSintomas(req.sintomas().trim());
        art.setCausa(req.causa().trim());
        art.setSolucion(req.solucion().trim());
        art.setCategoria(cat);
        if (req.activo() != null) art.setActivo(req.activo());
        if (req.verificado() != null) art.setVerificado(req.verificado());
    }

    private CasoDto toCasoDto(AnalisisCaso c) {
        return new CasoDto(
            c.getId(), c.getTitulo(), c.getDescripcion(),
            c.getCategoria().getId(), c.getCategoria().getNombre(),
            c.getPrioridad(), c.getEstado(),
            c.getFechaCreacion(), c.getFechaResolucion(),
            c.getUsuario().getId(), c.getUsuario().getNombre()
        );
    }

    private ArticuloDto toArticuloDto(ArticuloConocimiento a) {
        return new ArticuloDto(
            a.getId(), a.getTitulo(), a.getProblema(), a.getSintomas(), a.getCausa(), a.getSolucion(),
            a.getCategoria().getId(), a.getCategoria().getNombre(),
            a.isActivo(), a.isVerificado(),
            a.getFechaCreacion(), a.getFechaActualizacion()
        );
    }

    private static String validateEnum(String value, Set<String> allowed, String field) {
        String upper = String.valueOf(value).trim().toUpperCase(Locale.ROOT);
        if (!allowed.contains(upper)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Valor inválido para " + field + ": " + value);
        }
        return upper;
    }

    private static String normalizeFilter(String value) {
        return value == null || value.isBlank() || "ALL".equalsIgnoreCase(value) ? null : value.trim().toUpperCase(Locale.ROOT);
    }

    private static String normalizeSearch(String value) {
        return value == null || value.isBlank() ? null : value.trim();
    }

    private static Set<String> tokenize(String text) {
        if (text == null || text.isBlank()) return Set.of();
        String plain = Normalizer.normalize(text.toLowerCase(Locale.ROOT), Normalizer.Form.NFD)
            .replaceAll("\\p{M}+", "")
            .replaceAll("[^a-z0-9]+", " ");
        Set<String> tokens = new HashSet<>();
        for (String tok : plain.split("\\s+")) {
            if (tok.length() >= 4 && !STOPWORDS.contains(tok)) {
                tokens.add(tok);
            }
        }
        return tokens;
    }
}
