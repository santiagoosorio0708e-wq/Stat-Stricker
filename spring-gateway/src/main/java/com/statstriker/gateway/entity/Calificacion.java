package com.statstriker.gateway.entity;

import jakarta.persistence.*;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import java.time.LocalDateTime;

@Entity
@Table(name = "calificaciones")
public class Calificacion {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotNull
    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "respuesta_id", nullable = false, unique = true, foreignKey = @ForeignKey(name = "fk_calificacion_respuesta"))
    private RespuestaIA respuesta;

    @Min(1)
    @Max(5)
    @Column(nullable = false)
    private int puntuacion;

    @Column(length = 500)
    private String comentario = "";

    @Column(nullable = false)
    private LocalDateTime fecha;

    @PrePersist
    @PreUpdate
    void onSave() {
        if (fecha == null) {
            fecha = LocalDateTime.now();
        }
    }

    public Long getId() { return id; }
    public RespuestaIA getRespuesta() { return respuesta; }
    public void setRespuesta(RespuestaIA respuesta) { this.respuesta = respuesta; }
    public int getPuntuacion() { return puntuacion; }
    public void setPuntuacion(int puntuacion) { this.puntuacion = puntuacion; }
    public String getComentario() { return comentario; }
    public void setComentario(String comentario) { this.comentario = comentario != null ? comentario : ""; }
    public LocalDateTime getFecha() { return fecha; }
    public void setFecha(LocalDateTime fecha) { this.fecha = fecha; }
}
