# Business modules

Each directory represents a product capability, not a user role. A module owns its API boundary, application services, domain rules, and repository interfaces.

Modules may use `core`, `shared`, `ai`, and `infrastructure` through stable contracts. They must not reach into another module's persistence implementation.
