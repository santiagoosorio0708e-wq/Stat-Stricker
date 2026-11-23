# ============================================================
# StatStriker Spring Boot Gateway - Multi-stage build (Java 21)
# ============================================================
FROM maven:3.9.9-eclipse-temurin-21-alpine AS builder
WORKDIR /build

COPY spring-gateway/pom.xml ./pom.xml
RUN mvn -B -q dependency:go-offline

COPY spring-gateway/src ./src
RUN mvn -B -q package -DskipTests

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app

RUN addgroup -S appgroup && adduser -S appuser -G appgroup

COPY --from=builder /build/target/statstriker-gateway-1.0.0.jar /app/app.jar
COPY frontend /app/frontend

RUN chown -R appuser:appgroup /app
USER appuser

ENV SERVER_PORT=8011 \
    FRONTEND_DIR=file:/app/frontend/ \
    AI_ENGINE_URL=http://ai-engine:8011

EXPOSE 8011

HEALTHCHECK --interval=20s --timeout=4s --start-period=15s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8011/actuator/health | grep -q '"status":"UP"' || exit 1

ENTRYPOINT ["java", "-XX:+UseG1GC", "-XX:MaxRAMPercentage=75.0", "-jar", "/app/app.jar"]
