package com.statstriker.gateway.repository;

import com.statstriker.gateway.entity.ConsultaIA;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;

public interface ConsultaIARepository extends JpaRepository<ConsultaIA, Long> {
    List<ConsultaIA> findBySessionIdOrderByFechaAsc(String sessionId);
    boolean existsByAnalisisCasoId(Long analisisCasoId);
}
