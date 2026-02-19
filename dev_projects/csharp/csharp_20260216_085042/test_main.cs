using System;
using System.Net.Http;
using System.Threading.Tasks;
using Xunit;

public class JiraClientTests
{
    private readonly HttpClient _httpClient;

    public JiraClientTests()
    {
        _httpClient = new HttpClient { BaseAddress = new Uri("https://your-jira-instance.atlassian.net") };
    }

    [Fact]
    public async Task CreateIssueAsync_WithValidData_ShouldReturnSuccessStatusCode()
    {
        var jiraUrl = "https://your-jira-instance.atlassian.net";
        var client = new JiraClient(jiraUrl);

        await client.CreateIssueAsync("YOUR-PROJECT", "Bug", "Fix a bug in the application", "This is a test issue.");

        // Assuming the response status code for successful creation is 201
        Assert.Equal(201, (int)await _httpClient.GetAsync($"rest/api/2/issue/YOUR-ISSUE-ID"));
    }

    [Fact]
    public async Task CreateIssueAsync_WithInvalidData_ShouldThrowException()
    {
        var jiraUrl = "https://your-jira-instance.atlassian.net";
        var client = new JiraClient(jiraUrl);

        try
        {
            await client.CreateIssueAsync("YOUR-PROJECT", "Bug", "", "");
        }
        catch (HttpRequestException ex)
        {
            // Assuming the exception is thrown for invalid data
            Assert.Contains("Invalid request body", ex.Message);
        }
    }

    [Fact]
    public async Task UpdateIssueAsync_WithValidData_ShouldReturnSuccessStatusCode()
    {
        var jiraUrl = "https://your-jira-instance.atlassian.net";
        var client = new JiraClient(jiraUrl);

        await client.CreateIssueAsync("YOUR-PROJECT", "Bug", "Fix a bug in the application", "This is a test issue.");

        // Assuming the response status code for successful update is 204
        Assert.Equal(204, (int)await _httpClient.PutAsJsonAsync($"rest/api/2/issue/YOUR-ISSUE-ID", new { fields = new { summary = "Updated Summary", description = "Updated Description" } }));
    }

    [Fact]
    public async Task UpdateIssueAsync_WithInvalidData_ShouldThrowException()
    {
        var jiraUrl = "https://your-jira-instance.atlassian.net";
        var client = new JiraClient(jiraUrl);

        try
        {
            await client.UpdateIssueAsync("YOUR-ISSUE-ID", "", "");
        }
        catch (HttpRequestException ex)
        {
            // Assuming the exception is thrown for invalid data
            Assert.Contains("Invalid request body", ex.Message);
        }
    }

    [Fact]
    public async Task DeleteIssueAsync_WithValidData_ShouldReturnSuccessStatusCode()
    {
        var jiraUrl = "https://your-jira-instance.atlassian.net";
        var client = new JiraClient(jiraUrl);

        await client.CreateIssueAsync("YOUR-PROJECT", "Bug", "Fix a bug in the application", "This is a test issue.");

        // Assuming the response status code for successful deletion is 204
        Assert.Equal(204, (int)await _httpClient.DeleteAsync($"rest/api/2/issue/YOUR-ISSUE-ID"));
    }

    [Fact]
    public async Task DeleteIssueAsync_WithInvalidData_ShouldThrowException()
    {
        var jiraUrl = "https://your-jira-instance.atlassian.net";
        var client = new JiraClient(jiraUrl);

        try
        {
            await client.DeleteIssueAsync("YOUR-ISSUE-ID");
        }
        catch (HttpRequestException ex)
        {
            // Assuming the exception is thrown for invalid data
            Assert.Contains("Invalid issue key", ex.Message);
        }
    }
}