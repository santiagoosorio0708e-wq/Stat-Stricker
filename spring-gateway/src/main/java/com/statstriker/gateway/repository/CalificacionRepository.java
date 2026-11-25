package com.statstriker.gateway.repository;

import com.statstriker.gateway.entity.Calificacion;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface CalificacionRepository extends JpaRepository<Calificacion, Long> {
    Optional<Calificacion> findByRespuestaId(Long respuestaId);
}
