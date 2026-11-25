package com.statstriker.gateway.repository;

import com.statstriker.gateway.entity.FuenteRespuesta;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface FuenteRespuestaRepository extends JpaRepository<FuenteRespuesta, Long> {
    List<FuenteRespuesta> findByRespuestaId(Long respuestaId);
    boolean existsByArticuloId(Long articuloId);
}
