package com.statstriker.gateway.repository;

import com.statstriker.gateway.entity.ArticuloConocimiento;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface ArticuloConocimientoRepository extends JpaRepository<ArticuloConocimiento, Long> {

    @Query("""
        SELECT a FROM ArticuloConocimiento a
        JOIN FETCH a.categoria
        WHERE (:categoriaId IS NULL OR a.categoria.id = :categoriaId)
          AND (:activo IS NULL OR a.activo = :activo)
          AND (:q IS NULL OR LOWER(a.titulo) LIKE LOWER(CONCAT('%', :q, '%'))
               OR LOWER(a.problema) LIKE LOWER(CONCAT('%', :q, '%'))
               OR LOWER(a.solucion) LIKE LOWER(CONCAT('%', :q, '%')))
        ORDER BY a.activo DESC, a.fechaActualizacion DESC, a.id DESC
    """)
    List<ArticuloConocimiento> searchFiltered(
        @Param("categoriaId") Long categoriaId,
        @Param("activo") Boolean activo,
        @Param("q") String q
    );

    @Query("SELECT a FROM ArticuloConocimiento a JOIN FETCH a.categoria WHERE a.activo = true AND a.verificado = true")
    List<ArticuloConocimiento> findAllActiveAndVerified();
}
