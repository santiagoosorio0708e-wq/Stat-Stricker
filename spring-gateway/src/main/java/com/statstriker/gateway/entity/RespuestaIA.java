package com.statstriker.gateway.entity;

import jakarta.persistence.*;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.time.LocalDateTime;

@Entity
@Table(name = "respuestas_ia")
public class RespuestaIA {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotNull
    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "consulta_id", nullable = false, unique = true, foreignKey = @ForeignKey(name = "fk_respuesta_consulta"))
    private ConsultaIA consulta;

    @NotBlank
    @Column(nullable = false, columnDefinition = "TEXT")
    private String respuesta;

    @NotBlank
    @Column(nullable = false, length = 100)
    private String modelo;

    @Column(nullable = false)
    private LocalDateTime fecha;

    @PrePersist
    void onCreate() {
        if (fecha == null) {
            fecha = LocalDateTime.now();
        }
    }

    public Long getId() { return id; }
    public ConsultaIA getConsulta() { return consulta; }
    public void setConsulta(ConsultaIA consulta) { this.consulta = consulta; }
    public String getRespuesta() { return respuesta; }
    public void setRespuesta(String respuesta) { this.respuesta = respuesta; }
    public String getModelo() { return modelo; }
    public void setModelo(String modelo) { this.modelo = modelo; }
    public LocalDateTime getFecha() { return fecha; }
    public void setFecha(LocalDateTime fecha) { this.fecha = fecha; }
}
