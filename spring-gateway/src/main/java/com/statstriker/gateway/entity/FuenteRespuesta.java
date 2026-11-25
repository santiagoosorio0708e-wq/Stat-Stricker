package com.statstriker.gateway.entity;

import jakarta.persistence.*;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

@Entity
@Table(name = "fuentes_respuesta", indexes = {
    @Index(name = "idx_fuentes_respuesta", columnList = "respuesta_id")
})
public class FuenteRespuesta {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @NotNull
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "respuesta_id", nullable = false, foreignKey = @ForeignKey(name = "fk_fuente_respuesta"))
    private RespuestaIA respuesta;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "articulo_id", foreignKey = @ForeignKey(name = "fk_fuente_articulo"))
    private ArticuloConocimiento articulo;

    @NotBlank
    @Column(name = "titulo_fuente", nullable = false, length = 220)
    private String tituloFuente;

    @NotBlank
    @Column(nullable = false, length = 60)
    private String categoria = "rag";

    @Column(nullable = false)
    private double similitud = 0.0;

    public Long getId() { return id; }
    public RespuestaIA getRespuesta() { return respuesta; }
    public void setRespuesta(RespuestaIA respuesta) { this.respuesta = respuesta; }
    public ArticuloConocimiento getArticulo() { return articulo; }
    public void setArticulo(ArticuloConocimiento articulo) { this.articulo = articulo; }
    public String getTituloFuente() { return tituloFuente; }
    public void setTituloFuente(String tituloFuente) { this.tituloFuente = tituloFuente; }
    public String getCategoria() { return categoria; }
    public void setCategoria(String categoria) { this.categoria = categoria; }
    public double getSimilitud() { return similitud; }
    public void setSimilitud(double similitud) { this.similitud = similitud; }
}
