# TypeScript SDK Template

Complete structure and patterns for TypeScript SDK projects.

## Project Structure

```
service-sdk/
├── src/
│   ├── client.ts           # Main SDK client
│   ├── models.ts           # TypeScript interfaces
│   ├── exceptions.ts       # Custom error classes
│   ├── types.ts            # Type definitions
│   ├── utils.ts            # Utility functions
│   └── index.ts            # Package exports
├── tests/
│   ├── client.test.ts      # Client tests
│   └── models.test.ts      # Model tests
├── docs/
│   ├── README.md
│   └── api-reference.md
├── examples/
│   ├── quickstart.ts
│   └── advanced.ts
├── .github/
│   └── workflows/
│       ├── test.yml
│       └── publish.yml
├── package.json
├── tsconfig.json
├── jest.config.js
├── .eslintrc.json
├── .prettierrc
├── README.md
├── CHANGELOG.md
├── LICENSE
└── .gitignore
```

## package.json

```json
{
  "name": "@vecu/service-sdk",
  "version": "0.1.0",
  "description": "TypeScript SDK for Infiquetra Service API",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "files": [
    "dist",
    "README.md",
    "LICENSE"
  ],
  "scripts": {
    "build": "tsc",
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage",
    "lint": "eslint src/ --ext .ts",
    "lint:fix": "eslint src/ --ext .ts --fix",
    "format": "prettier --write \"src/**/*.ts\"",
    "prepublishOnly": "npm run build && npm test"
  },
  "keywords": [
    "vecu",
    "sdk",
    "vehicle-custody",
    "typescript"
  ],
  "author": "Infiquetra Team <hello@infiquetra.com>",
  "license": "MIT",
  "repository": {
    "type": "git",
    "url": "https://github.com/infiquetra/service-sdk"
  },
  "homepage": "https://documentation portal.vecu.example.com/service-sdk",
  "engines": {
    "node": ">=18.0.0"
  },
  "dependencies": {
    "axios": "^1.6.0",
    "axios-retry": "^4.0.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "@types/jest": "^29.0.0",
    "@typescript-eslint/eslint-plugin": "^6.0.0",
    "@typescript-eslint/parser": "^6.0.0",
    "eslint": "^8.0.0",
    "jest": "^29.0.0",
    "ts-jest": "^29.0.0",
    "typescript": "^5.3.0",
    "prettier": "^3.0.0"
  }
}
```

## tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "lib": ["ES2022"],
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist", "tests"]
}
```

## Client Pattern

```typescript
import axios, { AxiosInstance, AxiosError } from 'axios';
import axiosRetry from 'axios-retry';
import {
  Resource,
  CreateResourceRequest,
  ListResourcesOptions,
  ListResponse,
} from './models';
import {
  SDKError,
  AuthenticationError,
  ResourceNotFoundError,
  ValidationError,
} from './exceptions';

/**
 * Configuration options for the SDK client.
 */
export interface ClientConfig {
  /** Base URL of the API */
  baseUrl?: string;
  /** API key for authentication */
  apiKey: string;
  /** Request timeout in milliseconds */
  timeout?: number;
  /** Maximum number of retry attempts */
  maxRetries?: number;
}

/**
 * Client for interacting with Infiquetra Service API.
 *
 * @example
 * ```typescript
 * const client = new VECUServiceClient({ apiKey: 'your-api-key' });
 * const resource = await client.getResource('resource-id');
 * console.log(resource.name);
 * ```
 */
export class VECUServiceClient {
  private readonly axios: AxiosInstance;

  constructor(config: ClientConfig) {
    const {
      baseUrl = 'https://api.service.vecu.example.com',
      apiKey,
      timeout = 30000,
      maxRetries = 3,
    } = config;

    if (!apiKey) {
      throw new Error('API key is required');
    }

    this.axios = axios.create({
      baseURL: baseUrl,
      timeout,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
        'User-Agent': 'service-sdk/0.1.0',
      },
    });

    // Configure retry logic
    axiosRetry(this.axios, {
      retries: maxRetries,
      retryDelay: axiosRetry.exponentialDelay,
      retryCondition: (error) => {
        return axiosRetry.isNetworkOrIdempotentRequestError(error)
          || error.response?.status === 429; // Retry on rate limit
      },
    });

    // Add response interceptor for error handling
    this.axios.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => Promise.reject(this.handleError(error))
    );
  }

  /**
   * Gets a resource by ID.
   *
   * @param resourceId - The resource identifier
   * @returns The resource
   * @throws {AuthenticationError} When authentication fails
   * @throws {ResourceNotFoundError} When resource is not found
   * @throws {SDKError} For other API errors
   */
  async getResource(resourceId: string): Promise<Resource> {
    if (!resourceId) {
      throw new Error('Resource ID is required');
    }

    const response = await this.axios.get<Resource>(
      `/api/v1/resources/${resourceId}`
    );
    return response.data;
  }

  /**
   * Lists resources with pagination.
   *
   * @param options - List options (limit, offset, filters)
   * @returns List of resources
   */
  async listResources(
    options: ListResourcesOptions = {}
  ): Promise<ListResponse<Resource>> {
    const { limit = 100, offset = 0, filters } = options;

    const response = await this.axios.get<ListResponse<Resource>>(
      '/api/v1/resources',
      {
        params: {
          limit,
          offset,
          ...filters,
        },
      }
    );
    return response.data;
  }

  /**
   * Creates a new resource.
   *
   * @param request - Resource creation request
   * @returns The created resource
   */
  async createResource(request: CreateResourceRequest): Promise<Resource> {
    const response = await this.axios.post<Resource>(
      '/api/v1/resources',
      request
    );
    return response.data;
  }

  /**
   * Updates a resource.
   *
   * @param resourceId - The resource identifier
   * @param updates - Partial resource updates
   * @returns The updated resource
   */
  async updateResource(
    resourceId: string,
    updates: Partial<CreateResourceRequest>
  ): Promise<Resource> {
    const response = await this.axios.patch<Resource>(
      `/api/v1/resources/${resourceId}`,
      updates
    );
    return response.data;
  }

  /**
   * Deletes a resource.
   *
   * @param resourceId - The resource identifier
   */
  async deleteResource(resourceId: string): Promise<void> {
    await this.axios.delete(`/api/v1/resources/${resourceId}`);
  }

  private handleError(error: AxiosError): Error {
    if (!error.response) {
      return new SDKError(`Network error: ${error.message}`);
    }

    const { status, data } = error.response;
    const message = typeof data === 'string' ? data : JSON.stringify(data);

    switch (status) {
      case 401:
        return new AuthenticationError('Invalid or missing API key');
      case 404:
        return new ResourceNotFoundError('Resource not found');
      case 422:
        return new ValidationError(`Validation error: ${message}`);
      default:
        return new SDKError(`API error: ${status} - ${message}`);
    }
  }
}
```

## Models Pattern

```typescript
/**
 * Resource data model.
 */
export interface Resource {
  /** Resource identifier */
  id: string;
  /** Resource name */
  name: string;
  /** Resource description */
  description?: string;
  /** Resource status */
  status: 'active' | 'inactive' | 'archived';
  /** Creation timestamp */
  createdAt: string;
  /** Last update timestamp */
  updatedAt: string;
}

/**
 * Request model for creating a resource.
 */
export interface CreateResourceRequest {
  /** Resource name */
  name: string;
  /** Resource description */
  description?: string;
}

/**
 * Options for listing resources.
 */
export interface ListResourcesOptions {
  /** Maximum number of resources to return */
  limit?: number;
  /** Offset for pagination */
  offset?: number;
  /** Additional filters */
  filters?: Record<string, any>;
}

/**
 * Generic list response.
 */
export interface ListResponse<T> {
  /** List items */
  items: T[];
  /** Total count */
  total: number;
  /** Pagination limit */
  limit: number;
  /** Pagination offset */
  offset: number;
}
```

## Exception Pattern

```typescript
/**
 * Base error class for all SDK errors.
 */
export class SDKError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'SDKError';
    Object.setPrototypeOf(this, SDKError.prototype);
  }
}

/**
 * Error thrown when authentication fails.
 */
export class AuthenticationError extends SDKError {
  constructor(message: string) {
    super(message);
    this.name = 'AuthenticationError';
    Object.setPrototypeOf(this, AuthenticationError.prototype);
  }
}

/**
 * Error thrown when a resource is not found.
 */
export class ResourceNotFoundError extends SDKError {
  constructor(message: string) {
    super(message);
    this.name = 'ResourceNotFoundError';
    Object.setPrototypeOf(this, ResourceNotFoundError.prototype);
  }
}

/**
 * Error thrown when request validation fails.
 */
export class ValidationError extends SDKError {
  constructor(message: string) {
    super(message);
    this.name = 'ValidationError';
    Object.setPrototypeOf(this, ValidationError.prototype);
  }
}
```

## Testing Pattern (Jest)

```typescript
import { VECUServiceClient } from '../client';
import { Resource } from '../models';
import axios from 'axios';

jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('VECUServiceClient', () => {
  let client: VECUServiceClient;

  beforeEach(() => {
    client = new VECUServiceClient({ apiKey: 'test-key' });
    jest.clearAllMocks();
  });

  describe('getResource', () => {
    it('should return a resource', async () => {
      const mockResource: Resource = {
        id: 'res-123',
        name: 'Test Resource',
        status: 'active',
        createdAt: '2026-02-11T00:00:00Z',
        updatedAt: '2026-02-11T00:00:00Z',
      };

      mockedAxios.create.mockReturnValue({
        get: jest.fn().resolves({ data: mockResource }),
      } as any);

      const resource = await client.getResource('res-123');

      expect(resource).toEqual(mockResource);
      expect(resource.id).toBe('res-123');
    });

    it('should throw error for invalid ID', async () => {
      await expect(client.getResource('')).rejects.toThrow('Resource ID is required');
    });
  });
});
```

## Best Practices

1. **Strong typing** with interfaces throughout
2. **Async/await** for all I/O operations
3. **JSDoc comments** for documentation
4. **Axios interceptors** for error handling and retry logic
5. **Proper error hierarchy** with custom exception classes
6. **ESLint + Prettier** for code quality
7. **Jest** for comprehensive testing
8. **TypeScript strict mode** enabled
