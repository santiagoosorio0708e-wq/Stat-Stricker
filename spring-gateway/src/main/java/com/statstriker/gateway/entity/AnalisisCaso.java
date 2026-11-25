package com.statstriker.gateway.entity;

import jakarta.persistence.*;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.time.LocalDateTime;

@Entity
@Table(name = "analisis_casos", indexes = {
    @Index(name = "idx_casos_estado", columnList = "estado"),
    @Index(name = "idx_casos_prioridad", columnList = "prioridad"),
    @Index(name = "idx_casos_categoria", columnList = "categoria_id"),
    @Index(name = "idx_casos_fecha", columnList = "fecha_creacion")
})
public class AnalisisCaso {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank
    @Column(nullable = false, length = 180)
    private String titulo;

    @NotBlank
    @Column(nullable = false, columnDefinition = "TEXT")
    private String descripcion;

    @NotNull
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "categoria_id", nullable = false, foreignKey = @ForeignKey(name = "fk_caso_categoria"))
    private Categoria categoria;

    @NotBlank
    @Column(nullable = false, length = 20)
    private String prioridad = "MEDIA";

    @NotBlank
    @Column(nullable = false, length = 20)
    private String estado = "PENDIENTE";

    @Column(name = "fecha_creacion", nullable = false)
    private LocalDateTime fechaCreacion;

    @Column(name = "fecha_resolucion")
    private LocalDateTime fechaResolucion;

    @NotNull
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "usuario_id", nullable = false, foreignKey = @ForeignKey(name = "fk_caso_usuario"))
    private Usuario usuario;

    @PrePersist
    void onCreate() {
        if (fechaCreacion == null) {
            fechaCreacion = LocalDateTime.now();
        }
    }

    public Long getId() { return id; }
    public String getTitulo() { return titulo; }
    public void setTitulo(String titulo) { this.titulo = titulo; }
    public String getDescripcion() { return descripcion; }
    public void setDescripcion(String descripcion) { this.descripcion = descripcion; }
    public Categoria getCategoria() { return categoria; }
    public void setCategoria(Categoria categoria) { this.categoria = categoria; }
    public String getPrioridad() { return prioridad; }
    public void setPrioridad(String prioridad) { this.prioridad = prioridad; }
    public String getEstado() { return estado; }
    public void setEstado(String estado) { this.estado = estado; }
    public LocalDateTime getFechaCreacion() { return fechaCreacion; }
    public void setFechaCreacion(LocalDateTime fechaCreacion) { this.fechaCreacion = fechaCreacion; }
    public LocalDateTime getFechaResolucion() { return fechaResolucion; }
    public void setFechaResolucion(LocalDateTime fechaResolucion) { this.fechaResolucion = fechaResolucion; }
    public Usuario getUsuario() { return usuario; }
    public void setUsuario(Usuario usuario) { this.usuario = usuario; }
}
