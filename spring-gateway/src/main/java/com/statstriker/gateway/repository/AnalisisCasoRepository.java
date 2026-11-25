package com.statstriker.gateway.repository;

import com.statstriker.gateway.entity.AnalisisCaso;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface AnalisisCasoRepository extends JpaRepository<AnalisisCaso, Long> {

    @Query("""
        SELECT c FROM AnalisisCaso c
        JOIN FETCH c.categoria
        JOIN FETCH c.usuario
        WHERE (:categoriaId IS NULL OR c.categoria.id = :categoriaId)
          AND (:prioridad IS NULL OR c.prioridad = :prioridad)
          AND (:estado IS NULL OR c.estado = :estado)
          AND (:q IS NULL OR LOWER(c.titulo) LIKE LOWER(CONCAT('%', :q, '%'))
               OR LOWER(c.descripcion) LIKE LOWER(CONCAT('%', :q, '%')))
        ORDER BY c.fechaCreacion DESC, c.id DESC
    """)
    List<AnalisisCaso> searchFiltered(
        @Param("categoriaId") Long categoriaId,
        @Param("prioridad") String prioridad,
        @Param("estado") String estado,
        @Param("q") String q
    );
}
