# Storage/update integration tests

Run `dotnet run --project tools/project-storage-tests/ProjectStorageTests.csproj` with .NET 8.

This executes the actual project storage and update source using a test-only serializer and Unity value-type shim. It does not compile against the Unity SDK, validate JsonUtility in Unity, render anything or replace native Unity editor tests. Fixtures are original synthetic data, with no game assets.
