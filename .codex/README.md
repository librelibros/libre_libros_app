# Codex Project Requests

This folder defines the project delivery workflow used in this repository.

## What to ask for

If you want end-to-end execution, ask for the project in one message and say that it should be executed completely.

Recommended wording:

```text
Quiero que construyas este proyecto de punta a punta y ejecutes el flujo completo.
```

## What to include in the request

Include as much of this as possible:

1. Objective of the project
2. Target users
3. Main features or screens
4. Preferred stack, or say that Codex can choose
5. Data model, APIs, auth, or integrations if needed
6. Constraints: deadlines, deployment target, tests, performance, accessibility, languages
7. Definition of done: what must exist at the end

## Default UX behavior

If you do not specify a design direction:

- New projects default to Material Design
- Components should be basic and simple
- Layouts should be clear, responsive, and easy to implement
- Existing projects keep their current UI system unless you explicitly request a redesign

## What Codex will do

When you request full execution, the workflow is:

1. Define the feature specification
2. Analyze the codebase
3. Produce a UX specification
4. Create the technical plan
5. Implement the tasks
6. Validate the result

Artifacts are written under `generated/`.

## What you may still need to confirm

Some requests still require a confirmation before implementation:

- Ambiguous scope or missing business rules
- Destructive changes
- Access to external services, secrets, or deployments
- Major product decisions that materially change the project

The feature specification must be confirmed before development starts.

## Short request example

```text
Quiero que construyas una app web para gestionar libros.
Ejecuta el flujo completo.
Stack: Next.js + TypeScript.
Funciones: listado, detalle, busqueda y formulario de alta.
Diseno: usa el default del sistema.
Definition of done: app funcional con validacion basica y tests donde encajen.
```

## More complete request example

```text
Quiero que construyas de punta a punta un MVP de biblioteca personal y ejecutes el flujo completo.

Usuarios:
- lector individual

Stack:
- puedes usar Next.js, TypeScript y una base de datos ligera

Funciones:
- login simple
- listado de libros
- filtros por autor, genero y estado de lectura
- pantalla de detalle
- crear y editar libros
- dashboard con metricas basicas

Restricciones:
- responsive
- accesible
- sin dependencias innecesarias
- diseno basado en Material Design con componentes sencillos

Definition of done:
- proyecto ejecutable
- datos persistidos
- validaciones basicas
- pruebas minimas para las partes criticas
```
