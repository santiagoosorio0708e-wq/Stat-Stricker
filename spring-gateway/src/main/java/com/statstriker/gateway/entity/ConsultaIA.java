package com.statstriker.gateway.entity;

import jakarta.persistence.*;
import jakarta.validation.constraints.NotBlank;
import java.time.LocalDateTime;

@Entity
@Table(name = "consultas_ia", indexes = {
    @Index(name = "idx_consultas_session", columnList = "session_id, fecha"),
    @Index(name = "idx_consultas_estado", columnList = "estado")
})
public class ConsultaIA {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank
    @Column(name = "session_id", nullable = false, length = 80)
    private String sessionId;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "analisis_id", foreignKey = @ForeignKey(name = "fk_consulta_analisis"))
    private AnalisisCaso analisisCaso;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "usuario_id", foreignKey = @ForeignKey(name = "fk_consulta_usuario"))
    private Usuario usuario;

    @NotBlank
    @Column(nullable = false, columnDefinition = "TEXT")
    private String pregunta;

    @NotBlank
    @Column(nullable = false, length = 20)
    private String estado = "PENDIENTE";

    @Column(nullable = false)
    private LocalDateTime fecha;

    @PrePersist
    void onCreate() {
        if (fecha == null) {
            fecha = LocalDateTime.now();
        }
    }

    public Long getId() { return id; }
    public String getSessionId() { return sessionId; }
    public void setSessionId(String sessionId) { this.sessionId = sessionId; }
    public AnalisisCaso getAnalisisCaso() { return analisisCaso; }
    public void setAnalisisCaso(AnalisisCaso analisisCaso) { this.analisisCaso = analisisCaso; }
    public Usuario getUsuario() { return usuario; }
    public void setUsuario(Usuario usuario) { this.usuario = usuario; }
    public String getPregunta() { return pregunta; }
    public void setPregunta(String pregunta) { this.pregunta = pregunta; }
    public String getEstado() { return estado; }
    public void setEstado(String estado) { this.estado = estado; }
    public LocalDateTime getFecha() { return fecha; }
    public void setFecha(LocalDateTime fecha) { this.fecha = fecha; }
}
