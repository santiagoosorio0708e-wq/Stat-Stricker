package com.statstriker.gateway.entity;

import jakarta.persistence.*;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.time.LocalDateTime;

@Entity
@Table(name = "articulos_conocimiento", indexes = {
    @Index(name = "idx_articulos_activo", columnList = "activo, verificado"),
    @Index(name = "idx_articulos_categoria", columnList = "categoria_id")
})
public class ArticuloConocimiento {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank
    @Column(nullable = false, length = 180)
    private String titulo;

    @NotBlank
    @Column(nullable = false, columnDefinition = "TEXT")
    private String problema;

    @NotBlank
    @Column(nullable = false, columnDefinition = "TEXT")
    private String sintomas;

    @NotBlank
    @Column(nullable = false, columnDefinition = "TEXT")
    private String causa;

    @NotBlank
    @Column(nullable = false, columnDefinition = "TEXT")
    private String solucion;

    @NotNull
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "categoria_id", nullable = false, foreignKey = @ForeignKey(name = "fk_articulo_categoria"))
    private Categoria categoria;

    @Column(nullable = false)
    private boolean activo = true;

    @Column(nullable = false)
    private boolean verificado = true;

    @Column(name = "fecha_creacion", nullable = false)
    private LocalDateTime fechaCreacion;

    @Column(name = "fecha_actualizacion", nullable = false)
    private LocalDateTime fechaActualizacion;

    @PrePersist
    void onCreate() {
        LocalDateTime now = LocalDateTime.now();
        if (fechaCreacion == null) fechaCreacion = now;
        if (fechaActualizacion == null) fechaActualizacion = now;
    }

    @PreUpdate
    void onUpdate() {
        fechaActualizacion = LocalDateTime.now();
    }

    public Long getId() { return id; }
    public String getTitulo() { return titulo; }
    public void setTitulo(String titulo) { this.titulo = titulo; }
    public String getProblema() { return problema; }
    public void setProblema(String problema) { this.problema = problema; }
    public String getSintomas() { return sintomas; }
    public void setSintomas(String sintomas) { this.sintomas = sintomas; }
    public String getCausa() { return causa; }
    public void setCausa(String causa) { this.causa = causa; }
    public String getSolucion() { return solucion; }
    public void setSolucion(String solucion) { this.solucion = solucion; }
    public Categoria getCategoria() { return categoria; }
    public void setCategoria(Categoria categoria) { this.categoria = categoria; }
    public boolean isActivo() { return activo; }
    public void setActivo(boolean activo) { this.activo = activo; }
    public boolean isVerificado() { return verificado; }
    public void setVerificado(boolean verificado) { this.verificado = verificado; }
    public LocalDateTime getFechaCreacion() { return fechaCreacion; }
    public void setFechaCreacion(LocalDateTime fechaCreacion) { this.fechaCreacion = fechaCreacion; }
    public LocalDateTime getFechaActualizacion() { return fechaActualizacion; }
    public void setFechaActualizacion(LocalDateTime fechaActualizacion) { this.fechaActualizacion = fechaActualizacion; }
}
