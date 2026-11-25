package com.statstriker.gateway.config;

import com.statstriker.gateway.entity.*;
import com.statstriker.gateway.repository.*;
import java.time.LocalDateTime;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class SeedDataInitializer implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(SeedDataInitializer.class);

    private final UsuarioRepository usuarioRepo;
    private final CategoriaRepository categoriaRepo;
    private final AnalisisCasoRepository casoRepo;
    private final ArticuloConocimientoRepository articuloRepo;
    private final ConsultaIARepository consultaRepo;
    private final RespuestaIARepository respuestaRepo;
    private final FuenteRespuestaRepository fuenteRepo;
    private final CalificacionRepository calificacionRepo;

    public SeedDataInitializer(
        UsuarioRepository usuarioRepo,
        CategoriaRepository categoriaRepo,
        AnalisisCasoRepository casoRepo,
        ArticuloConocimientoRepository articuloRepo,
        ConsultaIARepository consultaRepo,
        RespuestaIARepository respuestaRepo,
        FuenteRespuestaRepository fuenteRepo,
        CalificacionRepository calificacionRepo
    ) {
        this.usuarioRepo = usuarioRepo;
        this.categoriaRepo = categoriaRepo;
        this.casoRepo = casoRepo;
        this.articuloRepo = articuloRepo;
        this.consultaRepo = consultaRepo;
        this.respuestaRepo = respuestaRepo;
        this.fuenteRepo = fuenteRepo;
        this.calificacionRepo = calificacionRepo;
    }

    @Override
    @Transactional
    public void run(ApplicationArguments args) {
        if (categoriaRepo.count() > 0) {
            return;
        }
        log.info("Sembrando datos iniciales relacionales JPA para StatStriker...");

        Usuario u1 = saveUser("Santiago Osorio", "santiago@statstriker.local", "Analítica Cuantitativa");
        Usuario u2 = saveUser("Laura Méndez", "laura@statstriker.local", "Mercados Europeos");
        Usuario u3 = saveUser("Carlos Ríos", "carlos@statstriker.local", "Gestión de Riesgo & Kelly");
        Usuario u4 = saveUser("Valentina Cruz", "valentina@statstriker.local", "Scouting de Jugadores");

        Categoria catPl = saveCategory("Premier League", "Partidos, goleadores y tendencias BTTS / +2.5 en Inglaterra", "39");
        Categoria catUcl = saveCategory("UEFA Champions League", "Fase de liga UEFA, alineaciones probables y cruces continentales", "2");
        Categoria catLiga = saveCategory("LaLiga", "Partidos de España, xG, córners y tendencias de goles", "140");
        Categoria catPlayers = saveCategory("Mercados de Jugadores", "Remates al arco, goles en cualquier momento y titularidades", "players");
        Categoria catRisk = saveCategory("Gestión de Riesgo y Cuotas", "Criterio de Kelly fraccional, EV positivo y validación de boletos", "risk");

        ArticuloConocimiento a1 = saveArticle(
            "Validación de mercado Ambos Marcan (BTTS) en Premier League",
            "Evaluar cuándo tiene valor real el mercado Ambos Marcan en ligas de ritmo alto.",
            "Equipos con promedio combinado ≥ 2.6 goles/partido y tasas de BTTS ≥ 60% en sus últimos 5 encuentros.",
            "Presión alta y transiciones rápidas generan ocasiones claras en ambas áreas cuando ambos conjuntos conceden ≥ 1.2 goles por juego.",
            "Verificar últimos 5 partidos (local y visitante), descartar bajas clave en ataque y exigir cuota ≥ 1/p (mínimo 1.67 si p=60%).",
            catPl, true, true
        );
        ArticuloConocimiento a2 = saveArticle(
            "Lectura objetiva de remates al arco para delanteros",
            "Identificar líneas rentables de +0.5 o +1.5 tiros al arco en jugadores titulares.",
            "El jugador promedia ≥ 1.2 tiros al arco en sus últimas 5 titularidades y ejecuta balón parado o penaltis.",
            "La línea +0.5 tiros al arco suele tener mayor regularidad estadística que apostar directamente a gol en partidos cerrados.",
            "Comprobar titularidad confirmada o último XI titular; priorizar +1.5 tiros al arco cuando el promedio supera 1.6/partido.",
            catPlayers, true, true
        );
        ArticuloConocimiento a3 = saveArticle(
            "Criterio de Kelly fraccional (1/4 de Kelly) y valor esperado (EV)",
            "Evitar sobre-apostar en combinadas o cuotas bajas sin respaldo matemático.",
            "Boleto con múltiples patas correlacionadas o cuotas menores a 1.35 sin ventaja estadística.",
            "El margen implícito de las casas penaliza combinadas largas y stakes altos frente a la varianza del fútbol.",
            "Calcular EV = (p × cuota) - 1; si EV <= 0 recomendar no entrar (0% stake); si EV > 0 limitar a 1/4 de Kelly (1% - 2.5% bankroll).",
            catRisk, true, true
        );
        ArticuloConocimiento a4 = saveArticle(
            "Factor localía y rotaciones en UEFA Champions League",
            "Ajustar probabilidades en fase de liga europea entre semana.",
            "Clubes con desgaste de calendario doméstico o bajas defensivas recientes en competición continental.",
            "Los equipos locales fuertes en fase liga suelen elevar su xG frente a rivales que viajan con rotaciones.",
            "Cruzar tabla oficial UEFA (posición, puntos, diferencia de goles) con la forma de los últimos 5 partidos y alineaciones.",
            catUcl, true, true
        );
        saveArticle(
            "Tendencia de goles +2.5 en LaLiga frente a bloques bajos",
            "Distinguir partidos abiertos de cruces cerrados en España.",
            "Duelo entre equipo con alta posesión y rival con ≥ 60% de porterías a cero recientes.",
            "Los bloques medios/bajos reducen los espacios y hacen que la media de goles caiga por debajo de 2.2.",
            "Priorizar Menos de 2.5 goles o hándicap asiático moderado cuando ambos equipos tengan < 40% en +2.5.",
            catLiga, true, true
        );
        saveArticle(
            "Detección de correlaciones negativas en boletos combinados",
            "Prevenir selecciones contradictorias dentro de una misma apuesta.",
            "Boleto que combina victoria de un equipo por hándicap -1.5 junto con Menos de 1.5 goles totales.",
            "Dos selecciones del mismo evento comparten dependencia estadística y pueden anularse mutuamente.",
            "Separar selecciones independientes, eliminar patas redundantes y recalcular la probabilidad conjunta real.",
            catRisk, true, true
        );
        saveArticle(
            "Borrador archivado de cuotas históricas 2024 (inactivo)",
            "Regla legada para cuotas de temporadas anteriores.",
            "Referencia desactualizada sin validez en la temporada 2026/27.",
            "Cambio de formato UEFA y plantillas renovadas.",
            "No utilizar como fuente activa en respuestas actuales.",
            catUcl, false, false
        );

        LocalDateTime now = LocalDateTime.now();
        List<AnalisisCaso> seededCases = List.of(
            buildCase("Brentford vs Everton · BTTS y +2.5 goles", "Análisis de racha ofensiva de Brentford en casa frente a defensa visitante.", catPl, "ALTA", "RESUELTO", now.minusDays(38), now.minusDays(38).plusHours(5), u1),
            buildCase("Arsenal vs Chelsea · Mercado 1X2 y remates", "Evaluación de titularidad y tiros al arco en derbi londinense.", catPl, "ALTA", "RESUELTO", now.minusDays(35), now.minusDays(35).plusHours(8), u2),
            buildCase("Real Madrid vs Barcelona · El Clásico", "Cruce completo con xG, tarjetas arbitrales y cuotas objetivas.", catLiga, "ALTA", "RESUELTO", now.minusDays(32), now.minusDays(31), u1),
            buildCase("Liverpool vs Manchester City · Duelo directo", "Comparativa de puntos en tabla, posesión y ambos marcan.", catPl, "ALTA", "CERRADO", now.minusDays(29), now.minusDays(28), u3),
            buildCase("Bayern Munich vs Inter · Fase liga UCL", "Revisión de alineaciones probables y goles en primera mitad.", catUcl, "MEDIA", "RESUELTO", now.minusDays(26), now.minusDays(26).plusHours(12), u2),
            buildCase("PSG vs Arsenal · Choque de bombos UEFA", "Impacto de bajas confirmadas y cuota mínima justa 1/p.", catUcl, "ALTA", "RESUELTO", now.minusDays(23), now.minusDays(22), u4),
            buildCase("Atlético Madrid vs Villarreal · Under 2.5", "Análisis defensivo en LaLiga y frecuencia de porterías a cero.", catLiga, "MEDIA", "RESUELTO", now.minusDays(21), now.minusDays(21).plusHours(6), u3),
            buildCase("Aston Villa vs Nottingham Forest · Tabla PL", "Cruce de posición, puntos actuales y racha últimos 5 partidos.", catPl, "MEDIA", "RESUELTO", now.minusDays(18), now.minusDays(18).plusHours(4), u1),
            buildCase("Propuesta tiros al arco · Igor Thiago", "Seguimiento de remates totales vs al arco en los últimos 5 duelos.", catPlayers, "MEDIA", "RESUELTO", now.minusDays(16), now.minusDays(16).plusHours(3), u4),
            buildCase("Validación boleto combinado 4 selecciones", "Revisión de correlaciones y ajuste de stake con 1/4 de Kelly.", catRisk, "ALTA", "CERRADO", now.minusDays(14), now.minusDays(13), u3),
            buildCase("Millonarios vs Benfica · Comparativa internacional", "Búsqueda externa de últimos 5 encuentros fuera de ligas top.", catRisk, "BAJA", "RESUELTO", now.minusDays(12), now.minusDays(12).plusHours(7), u2),
            buildCase("Real Sociedad vs Betis · Córners y tarjetas", "Evaluación estadística de saques de esquina en LaLiga.", catLiga, "BAJA", "RESUELTO", now.minusDays(10), now.minusDays(10).plusHours(9), u1),
            buildCase("Propuesta gol en cualquier momento · Haaland", "Validación de contexto y frecuencia goleadora reciente.", catPlayers, "ALTA", "RESUELTO", now.minusDays(8), now.minusDays(8).plusHours(2), u4),
            buildCase("Benfica vs Porto · Clásico portugués", "Estudio de mercado doble oportunidad y valor esperado.", catUcl, "MEDIA", "EN_ANALISIS", now.minusDays(6), null, u2),
            buildCase("Valencia vs Sevilla · Riesgo de empate 1X2", "Tendencia reciente de empates en zona media de LaLiga.", catLiga, "MEDIA", "RESUELTO", now.minusDays(5), now.minusDays(5).plusHours(6), u3),
            buildCase("Newcastle vs Brighton · +1.5 tiros al arco", "Selección de jugadores más rentables según alineación probable.", catPlayers, "ALTA", "EN_ANALISIS", now.minusDays(4), null, u4),
            buildCase("Control de bankroll semanal (límite 2%)", "Auditoría de stakes aplicados en apuestas de cuota ≥ 1.80.", catRisk, "ALTA", "RESUELTO", now.minusDays(3), now.minusDays(3).plusHours(4), u3),
            buildCase("Juventus vs Milan · Bajo riesgo conservador", "Evaluación de doble oportunidad y menos de 3.5 goles.", catUcl, "BAJA", "PENDIENTE", now.minusDays(2), null, u2),
            buildCase("Tottenham vs West Ham · Derbi de goles", "Revisión de promedio de goles y BTTS en los últimos 5 juegos.", catPl, "MEDIA", "PENDIENTE", now.minusDays(1), null, u1),
            buildCase("Alineaciones probables jornada europea", "Cruce de XI iniciales y jugadores con mayor EV de remate.", catUcl, "ALTA", "EN_ANALISIS", now.minusHours(12), null, u4)
        );
        casoRepo.saveAll(seededCases);

        ConsultaIA c1 = saveQuery("seed-1", seededCases.get(0), u1, "¿Conviene apostar Ambos Marcan en Brentford vs Everton?", "RESPONDIDA", now.minusDays(7));
        RespuestaIA r1 = saveAnswer(c1, "Sí tiene respaldo estadístico moderado según racha BTTS y promedio de goles; exige cuota mínima justa ≥ 1.67.", "gemini:gemini-3.5-flash-lite", now.minusDays(7));
        saveSource(r1, a1, a1.getTitulo(), "conocimiento_verificado", 0.91);
        saveRating(r1, 5, "Muy clara la cuota mínima justa y el cruce de los últimos 5 partidos.", now.minusDays(7));

        ConsultaIA c2 = saveQuery("seed-2", seededCases.get(8), u4, "¿Qué jugadores de Aston Villa vs Everton son más rentables para remates?", "RESPONDIDA", now.minusDays(5));
        RespuestaIA r2 = saveAnswer(c2, "Según las alineaciones recientes, los delanteros titulares superan 1.2 tiros al arco/partido.", "gemini:gemini-3.5-flash-lite", now.minusDays(5));
        saveSource(r2, a2, a2.getTitulo(), "conocimiento_verificado", 0.88);
        saveRating(r2, 5, "Útil mostrar los dos once iniciales y sus promedios.", now.minusDays(5));

        ConsultaIA c3 = saveQuery("seed-3", seededCases.get(9), u3, "Analiza esta combinada de 4 patas con cuota 9.40", "RESPONDIDA", now.minusDays(3));
        RespuestaIA r3 = saveAnswer(c3, "Contiene correlación negativa entre líneas; recomienda reducir stake con 1/4 de Kelly.", "gemini:gemini-3.5-flash-lite", now.minusDays(3));
        saveSource(r3, a3, a3.getTitulo(), "conocimiento_verificado", 0.93);
        saveRating(r3, 4, "Detectó rápido el riesgo de la combinada.", now.minusDays(3));

        ConsultaIA c4 = saveQuery("seed-4", null, u2, "¿Cómo viene Equipo Inexistente FC en tercera división?", "SIN_RESULTADOS", now.minusDays(2));
        RespuestaIA r4 = saveAnswer(c4, "No existen datos verificados para Equipo Inexistente FC; no se generan cifras inventadas.", "gemini:gemini-3.5-flash-lite", now.minusDays(2));
        saveRating(r4, 4, "Correcto al reconocer falta de fuentes.", now.minusDays(2));

        ConsultaIA c5 = saveQuery("seed-5", seededCases.get(4), u2, "Alineaciones y valor en Champions League", "RESPONDIDA", now.minusDays(1));
        RespuestaIA r5 = saveAnswer(c5, "Tabla oficial UEFA verificada junto a titulares de los últimos encuentros.", "gemini:gemini-3.5-flash-lite", now.minusDays(1));
        saveSource(r5, a4, a4.getTitulo(), "conocimiento_verificado", 0.86);
        saveRating(r5, 5, "Excelente precisión en tabla UEFA.", now.minusDays(1));

        saveQuery("seed-6", null, u1, "Prueba de fallo controlado de embeddings", "ERROR", now.minusHours(8));
    }

    private Usuario saveUser(String nombre, String correo, String area) {
        Usuario u = new Usuario();
        u.setNombre(nombre);
        u.setCorreo(correo);
        u.setArea(area);
        return usuarioRepo.save(u);
    }

    private Categoria saveCategory(String nombre, String descripcion, String ligaCodigo) {
        Categoria c = new Categoria();
        c.setNombre(nombre);
        c.setDescripcion(descripcion);
        c.setLigaCodigo(ligaCodigo);
        return categoriaRepo.save(c);
    }

    private ArticuloConocimiento saveArticle(
        String titulo, String problema, String sintomas, String causa, String solucion,
        Categoria cat, boolean activo, boolean verificado
    ) {
        ArticuloConocimiento a = new ArticuloConocimiento();
        a.setTitulo(titulo);
        a.setProblema(problema);
        a.setSintomas(sintomas);
        a.setCausa(causa);
        a.setSolucion(solucion);
        a.setCategoria(cat);
        a.setActivo(activo);
        a.setVerificado(verificado);
        return articuloRepo.save(a);
    }

    private AnalisisCaso buildCase(
        String titulo, String descripcion, Categoria cat, String prioridad, String estado,
        LocalDateTime creacion, LocalDateTime resolucion, Usuario usuario
    ) {
        AnalisisCaso c = new AnalisisCaso();
        c.setTitulo(titulo);
        c.setDescripcion(descripcion);
        c.setCategoria(cat);
        c.setPrioridad(prioridad);
        c.setEstado(estado);
        c.setFechaCreacion(creacion);
        c.setFechaResolucion(resolucion);
        c.setUsuario(usuario);
        return c;
    }

    private ConsultaIA saveQuery(String sid, AnalisisCaso caso, Usuario user, String pregunta, String estado, LocalDateTime fecha) {
        ConsultaIA q = new ConsultaIA();
        q.setSessionId(sid);
        q.setAnalisisCaso(caso);
        q.setUsuario(user);
        q.setPregunta(pregunta);
        q.setEstado(estado);
        q.setFecha(fecha);
        return consultaRepo.save(q);
    }

    private RespuestaIA saveAnswer(ConsultaIA q, String text, String modelo, LocalDateTime fecha) {
        RespuestaIA r = new RespuestaIA();
        r.setConsulta(q);
        r.setRespuesta(text);
        r.setModelo(modelo);
        r.setFecha(fecha);
        return respuestaRepo.save(r);
    }

    private void saveSource(RespuestaIA r, ArticuloConocimiento art, String titulo, String cat, double sim) {
        FuenteRespuesta f = new FuenteRespuesta();
        f.setRespuesta(r);
        f.setArticulo(art);
        f.setTituloFuente(titulo);
        f.setCategoria(cat);
        f.setSimilitud(sim);
        fuenteRepo.save(f);
    }

    private void saveRating(RespuestaIA r, int score, String comment, LocalDateTime fecha) {
        Calificacion cal = new Calificacion();
        cal.setRespuesta(r);
        cal.setPuntuacion(score);
        cal.setComentario(comment);
        cal.setFecha(fecha);
        calificacionRepo.save(cal);
    }
}
