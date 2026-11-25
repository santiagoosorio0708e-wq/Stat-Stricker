package com.statstriker.gateway.entity;

import jakarta.persistence.*;
import jakarta.validation.constraints.NotBlank;

@Entity
@Table(name = "categorias", indexes = {
    @Index(name = "idx_categorias_nombre", columnList = "nombre")
})
public class Categoria {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotBlank
    @Column(nullable = false, unique = true, length = 100)
    private String nombre;

    @NotBlank
    @Column(nullable = false, length = 300)
    private String descripcion;

    @Column(name = "liga_codigo", length = 32)
    private String ligaCodigo = "";

    public Long getId() { return id; }
    public String getNombre() { return nombre; }
    public void setNombre(String nombre) { this.nombre = nombre; }
    public String getDescripcion() { return descripcion; }
    public void setDescripcion(String descripcion) { this.descripcion = descripcion; }
    public String getLigaCodigo() { return ligaCodigo; }
    public void setLigaCodigo(String ligaCodigo) { this.ligaCodigo = ligaCodigo != null ? ligaCodigo : ""; }
}
