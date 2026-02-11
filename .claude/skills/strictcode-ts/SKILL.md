---
name: strictcode-ts
description: TypeScript-specific coding standards and idioms. Invoked by strictcode coordinator or directly for TypeScript files.
allowed-tools: Read, Write, Edit, Glob, Grep, mcp__mcp-exec__*
---

# StrictCode TypeScript - Language-Specific Standards

**Version:** 1.0.0
**Purpose:** Enforce TypeScript idioms and patterns on `.ts` and `.tsx` files.

---

## TypeScript Idioms (MANDATORY)

### Type Safety
- **Strict mode always** — `"strict": true` in tsconfig.json
- **No `any` type** — Use `unknown` and narrow, or define proper types
- **Explicit return types** on exported functions
- **Discriminated unions** over type assertions

### Null Handling
- **Optional chaining** (`?.`) instead of nested null checks
- **Nullish coalescing** (`??`) instead of `|| defaultValue`
- **Non-null assertion (!)** only when you've verified safety

### Switch Statements
- **Exhaustive checks** — Never use `default` that swallows cases
- Use `assertNever` pattern for compile-time exhaustiveness

### Patterns
- `const` assertions where applicable
- Type inference where type is obvious from assignment
- Object shorthand (`{ name }` not `{ name: name }`)
- Arrow functions for callbacks
- Template literals over string concatenation

---

## Reduction Patterns (APPLY)

| Pattern | Before | After |
|---------|--------|-------|
| Optional chaining | `user && user.profile && user.profile.name` | `user?.profile?.name` |
| Nullish coalescing | `value \|\| 'default'` | `value ?? 'default'` |
| Object shorthand | `{ name: name, age: age }` | `{ name, age }` |
| Template literal | `'Hello ' + name + '!'` | `` `Hello ${name}!` `` |
| Arrow callback | `items.map(function(x) { return x * 2; })` | `items.map(x => x * 2)` |
| Type inference | `const x: number = 5` | `const x = 5` |

---

## Example: Before/After

```typescript
// BEFORE (violations: any, verbose null checks, no return type)
function getDisplayName(user: any) {
    if (user !== null && user !== undefined) {
        if (user.profile !== null && user.profile !== undefined) {
            if (user.profile.displayName !== null && user.profile.displayName !== undefined) {
                return user.profile.displayName;
            }
        }
    }
    return "Anonymous";
}
```

```typescript
// AFTER (typed, optional chaining, nullish coalescing, return type)
interface User {
    profile?: {
        displayName?: string;
    };
}

function getDisplayName(user: User | null | undefined): string {
    return user?.profile?.displayName ?? "Anonymous";
}
```

---

## Discriminated Union Pattern

```typescript
// Define discriminated union
type Result<T> =
    | { success: true; data: T }
    | { success: false; error: string };

// Usage with exhaustive handling
function handleResult<T>(result: Result<T>): T | never {
    if (result.success) {
        return result.data;
    }
    throw new Error(result.error);
}

// Exhaustive switch
type Status = 'pending' | 'active' | 'completed' | 'failed';

function assertNever(x: never): never {
    throw new Error(`Unexpected value: ${x}`);
}

function getStatusLabel(status: Status): string {
    switch (status) {
        case 'pending': return 'Pending';
        case 'active': return 'Active';
        case 'completed': return 'Done';
        case 'failed': return 'Failed';
        default: return assertNever(status); // Compile error if case missing
    }
}
```

---

## Const Assertion Pattern

```typescript
// Without const assertion - type is string[]
const colors = ['red', 'green', 'blue'];

// With const assertion - type is readonly ['red', 'green', 'blue']
const colors = ['red', 'green', 'blue'] as const;

// Useful for creating literal union types
type Color = typeof colors[number]; // 'red' | 'green' | 'blue'

// Object const assertion
const config = {
    apiUrl: 'https://api.example.com',
    timeout: 5000,
} as const;
// config.apiUrl is type 'https://api.example.com', not string
```

---

## Type Narrowing Patterns

```typescript
// Type guard function
function isString(value: unknown): value is string {
    return typeof value === 'string';
}

// Usage
function process(value: unknown): string {
    if (isString(value)) {
        return value.toUpperCase(); // TypeScript knows it's string
    }
    throw new Error('Expected string');
}

// In operator narrowing
interface Dog { bark(): void; }
interface Cat { meow(): void; }

function speak(animal: Dog | Cat): void {
    if ('bark' in animal) {
        animal.bark();
    } else {
        animal.meow();
    }
}
```

---

## Checklist

Before completing TypeScript code changes:

- [ ] No `any` type — use `unknown` or proper types
- [ ] Explicit return types on exported functions
- [ ] Optional chaining (`?.`) for null checks
- [ ] Nullish coalescing (`??`) not `||` for defaults
- [ ] Discriminated unions for variant types
- [ ] Exhaustive switch with `assertNever`
- [ ] `as const` for literal types
- [ ] Object shorthand used
- [ ] Template literals (not string concatenation)
- [ ] Arrow functions for callbacks
