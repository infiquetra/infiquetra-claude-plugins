# .NET SDK Template

Complete structure and patterns for .NET SDK projects targeting .NET 8.0+.

## Project Structure

```
infiquetra.Service.SDK/
├── src/
│   └── infiquetra.Service.SDK/
│       ├── Client.cs              # Main SDK client
│       ├── Models/
│       │   ├── Resource.cs        # Data models
│       │   └── CreateResourceRequest.cs
│       ├── Exceptions/
│       │   ├── SDKException.cs
│       │   └── AuthenticationException.cs
│       ├── Http/
│       │   └── RetryHandler.cs    # HTTP retry logic
│       └── infiquetra.Service.SDK.csproj
├── tests/
│   └── infiquetra.Service.SDK.Tests/
│       ├── ClientTests.cs
│       ├── ModelTests.cs
│       └── infiquetra.Service.SDK.Tests.csproj
├── examples/
│   └── Quickstart/
│       ├── Program.cs
│       └── Quickstart.csproj
├── docs/
│   ├── README.md
│   └── api-reference.md
├── .github/
│   └── workflows/
│       ├── test.yml
│       └── publish.yml
├── infiquetra.Service.SDK.sln
├── README.md
├── CHANGELOG.md
├── LICENSE
└── .gitignore
```

## Project File (.csproj)

```xml
<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <LangVersion>latest</LangVersion>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>

    <!-- NuGet Package Metadata -->
    <PackageId>infiquetra.Service.SDK</PackageId>
    <Version>0.1.0</Version>
    <Authors>Infiquetra Team</Authors>
    <Company>your organization</Company>
    <Product>Infiquetra Service SDK</Product>
    <Description>C# SDK for Infiquetra Service API</Description>
    <PackageTags>vecu;sdk;vehicle-custody</PackageTags>
    <PackageLicenseExpression>MIT</PackageLicenseExpression>
    <PackageProjectUrl>https://github.com/infiquetra/service-sdk</PackageProjectUrl>
    <RepositoryUrl>https://github.com/infiquetra/service-sdk</RepositoryUrl>
    <RepositoryType>git</RepositoryType>

    <!-- Documentation -->
    <GenerateDocumentationFile>true</GenerateDocumentationFile>
    <DocumentationFile>bin\$(Configuration)\$(TargetFramework)\$(AssemblyName).xml</DocumentationFile>
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="Microsoft.Extensions.Http" Version="8.0.0" />
    <PackageReference Include="Microsoft.Extensions.Http.Polly" Version="8.0.0" />
    <PackageReference Include="System.Text.Json" Version="8.0.0" />
  </ItemGroup>

</Project>
```

## Client Pattern

```csharp
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;

namespace infiquetra.Service.SDK;

/// <summary>
/// Client for interacting with Infiquetra Service API.
/// </summary>
/// <example>
/// <code>
/// using var client = new ServiceClient("your-api-key");
/// var resource = await client.GetResourceAsync("resource-id");
/// Console.WriteLine(resource.Name);
/// </code>
/// </example>
public class ServiceClient : IDisposable
{
    private readonly HttpClient _httpClient;
    private readonly string _apiKey;
    private readonly JsonSerializerOptions _jsonOptions;

    /// <summary>
    /// Initializes a new instance of the ServiceClient class.
    /// </summary>
    /// <param name="apiKey">API key for authentication</param>
    /// <param name="baseUrl">Base URL of the API (optional)</param>
    /// <param name="httpClient">Custom HttpClient instance (optional)</param>
    public ServiceClient(
        string apiKey,
        string? baseUrl = null,
        HttpClient? httpClient = null)
    {
        _apiKey = apiKey ?? throw new ArgumentNullException(nameof(apiKey));
        _httpClient = httpClient ?? new HttpClient();
        _httpClient.BaseAddress = new Uri(baseUrl ?? "https://api.service.vecu.example.com");
        _httpClient.DefaultRequestHeaders.Authorization =
            new AuthenticationHeaderValue("Bearer", _apiKey);
        _httpClient.DefaultRequestHeaders.Add("User-Agent", "service-sdk/0.1.0");

        _jsonOptions = new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
            PropertyNameCaseInsensitive = true,
        };
    }

    /// <summary>
    /// Gets a resource by ID.
    /// </summary>
    /// <param name="resourceId">The resource identifier</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>The resource</returns>
    /// <exception cref="AuthenticationException">Thrown when authentication fails</exception>
    /// <exception cref="ResourceNotFoundException">Thrown when resource is not found</exception>
    /// <exception cref="SDKException">Thrown for other API errors</exception>
    public async Task<Resource> GetResourceAsync(
        string resourceId,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(resourceId))
            throw new ArgumentException("Resource ID cannot be empty", nameof(resourceId));

        var response = await _httpClient.GetAsync(
            $"/api/v1/resources/{resourceId}",
            cancellationToken);

        await EnsureSuccessStatusCodeAsync(response);

        return await response.Content.ReadFromJsonAsync<Resource>(
            _jsonOptions,
            cancellationToken)
            ?? throw new SDKException("Failed to deserialize response");
    }

    /// <summary>
    /// Lists resources with pagination.
    /// </summary>
    /// <param name="limit">Maximum number of resources to return</param>
    /// <param name="offset">Offset for pagination</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>List of resources</returns>
    public async Task<IReadOnlyList<Resource>> ListResourcesAsync(
        int limit = 100,
        int offset = 0,
        CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync(
            $"/api/v1/resources?limit={limit}&offset={offset}",
            cancellationToken);

        await EnsureSuccessStatusCodeAsync(response);

        var result = await response.Content.ReadFromJsonAsync<ListResponse<Resource>>(
            _jsonOptions,
            cancellationToken)
            ?? throw new SDKException("Failed to deserialize response");

        return result.Items;
    }

    /// <summary>
    /// Creates a new resource.
    /// </summary>
    /// <param name="request">Resource creation request</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>The created resource</returns>
    public async Task<Resource> CreateResourceAsync(
        CreateResourceRequest request,
        CancellationToken cancellationToken = default)
    {
        if (request == null)
            throw new ArgumentNullException(nameof(request));

        var response = await _httpClient.PostAsJsonAsync(
            "/api/v1/resources",
            request,
            _jsonOptions,
            cancellationToken);

        await EnsureSuccessStatusCodeAsync(response);

        return await response.Content.ReadFromJsonAsync<Resource>(
            _jsonOptions,
            cancellationToken)
            ?? throw new SDKException("Failed to deserialize response");
    }

    private static async Task EnsureSuccessStatusCodeAsync(HttpResponseMessage response)
    {
        if (response.IsSuccessStatusCode)
            return;

        var content = await response.Content.ReadAsStringAsync();

        throw response.StatusCode switch
        {
            HttpStatusCode.Unauthorized => new AuthenticationException("Invalid or missing API key"),
            HttpStatusCode.NotFound => new ResourceNotFoundException("Resource not found"),
            HttpStatusCode.UnprocessableEntity => new ValidationException($"Validation error: {content}"),
            _ => new SDKException($"API error: {response.StatusCode} - {content}")
        };
    }

    public void Dispose()
    {
        _httpClient?.Dispose();
    }
}
```

## Models Pattern

```csharp
using System.Text.Json.Serialization;

namespace infiquetra.Service.SDK.Models;

/// <summary>
/// Represents a resource.
/// </summary>
public record Resource
{
    /// <summary>
    /// Resource identifier.
    /// </summary>
    [JsonPropertyName("id")]
    public required string Id { get; init; }

    /// <summary>
    /// Resource name.
    /// </summary>
    [JsonPropertyName("name")]
    public required string Name { get; init; }

    /// <summary>
    /// Resource description.
    /// </summary>
    [JsonPropertyName("description")]
    public string? Description { get; init; }

    /// <summary>
    /// Resource status.
    /// </summary>
    [JsonPropertyName("status")]
    public string Status { get; init; } = "active";

    /// <summary>
    /// Creation timestamp.
    /// </summary>
    [JsonPropertyName("created_at")]
    public DateTime CreatedAt { get; init; }

    /// <summary>
    /// Last update timestamp.
    /// </summary>
    [JsonPropertyName("updated_at")]
    public DateTime UpdatedAt { get; init; }
}

/// <summary>
/// Request model for creating a resource.
/// </summary>
public record CreateResourceRequest
{
    /// <summary>
    /// Resource name.
    /// </summary>
    [JsonPropertyName("name")]
    public required string Name { get; init; }

    /// <summary>
    /// Resource description.
    /// </summary>
    [JsonPropertyName("description")]
    public string? Description { get; init; }
}
```

## Exception Pattern

```csharp
namespace infiquetra.Service.SDK.Exceptions;

/// <summary>
/// Base exception for all SDK errors.
/// </summary>
public class SDKException : Exception
{
    public SDKException() { }
    public SDKException(string message) : base(message) { }
    public SDKException(string message, Exception inner) : base(message, inner) { }
}

/// <summary>
/// Exception thrown when authentication fails.
/// </summary>
public class AuthenticationException : SDKException
{
    public AuthenticationException() { }
    public AuthenticationException(string message) : base(message) { }
}

/// <summary>
/// Exception thrown when a resource is not found.
/// </summary>
public class ResourceNotFoundException : SDKException
{
    public ResourceNotFoundException() { }
    public ResourceNotFoundException(string message) : base(message) { }
}
```

## Testing Pattern (xUnit)

```csharp
using Xunit;
using Moq;
using Moq.Protected;

namespace infiquetra.Service.SDK.Tests;

public class ClientTests
{
    [Fact]
    public async Task GetResourceAsync_ReturnsResource()
    {
        // Arrange
        var mockHttp = new Mock<HttpMessageHandler>();
        mockHttp.Protected()
            .Setup<Task<HttpResponseMessage>>(
                "SendAsync",
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>())
            .ReturnsAsync(new HttpResponseMessage
            {
                StatusCode = HttpStatusCode.OK,
                Content = new StringContent(@"{
                    ""id"": ""res-123"",
                    ""name"": ""Test Resource"",
                    ""status"": ""active"",
                    ""created_at"": ""2026-02-11T00:00:00Z"",
                    ""updated_at"": ""2026-02-11T00:00:00Z""
                }")
            });

        var httpClient = new HttpClient(mockHttp.Object);
        var client = new ServiceClient("test-key", httpClient: httpClient);

        // Act
        var resource = await client.GetResourceAsync("res-123");

        // Assert
        Assert.Equal("res-123", resource.Id);
        Assert.Equal("Test Resource", resource.Name);
    }
}
```

## Best Practices

1. **Use records** for immutable data models
2. **Async/await** throughout for I/O operations
3. **XML documentation comments** for IntelliSense
4. **Nullable reference types** enabled
5. **Dependency injection** support with IHttpClientFactory
6. **Polly** for retry and resilience policies
7. **System.Text.Json** for serialization
8. **IDisposable** for resource cleanup
