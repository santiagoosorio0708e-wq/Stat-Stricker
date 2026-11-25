package com.statstriker.gateway.repository;

import com.statstriker.gateway.entity.RespuestaIA;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface RespuestaIARepository extends JpaRepository<RespuestaIA, Long> {
    Optional<RespuestaIA> findByConsultaId(Long consultaId);
}
