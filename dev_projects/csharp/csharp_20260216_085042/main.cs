using System;
using System.Net.Http;
using System.Threading.Tasks;

public class JiraClient
{
    private readonly HttpClient _httpClient;

    public JiraClient(string jiraUrl)
    {
        _httpClient = new HttpClient { BaseAddress = new Uri(jiraUrl) };
    }

    public async Task CreateIssueAsync(string projectKey, string issueType, string summary, string description)
    {
        var requestBody = new
        {
            fields = new
            {
                project = new { key = projectKey },
                issuetype = new { name = issueType },
                summary = summary,
                description = description
            }
        };

        var response = await _httpClient.PostAsJsonAsync("rest/api/2/issue", requestBody);
        response.EnsureSuccessStatusCode();
    }

    public async Task UpdateIssueAsync(string issueKey, string summary, string description)
    {
        var requestBody = new
        {
            fields = new
            {
                summary = summary,
                description = description
            }
        };

        var response = await _httpClient.PutAsJsonAsync($"rest/api/2/issue/{issueKey}", requestBody);
        response.EnsureSuccessStatusCode();
    }

    public async Task DeleteIssueAsync(string issueKey)
    {
        var response = await _httpClient.DeleteAsync($"rest/api/2/issue/{issueKey}");
        response.EnsureSuccessStatusCode();
    }
}

public class Program
{
    public static async Task Main(string[] args)
    {
        var jiraUrl = "https://your-jira-instance.atlassian.net";
        var client = new JiraClient(jiraUrl);

        try
        {
            await client.CreateIssueAsync("YOUR-PROJECT", "Bug", "Fix a bug in the application", "This is a test issue.");
            Console.WriteLine("Issue created successfully.");

            await client.UpdateIssueAsync("YOUR-ISSUE-ID", "Updated Summary", "Updated Description");
            Console.WriteLine("Issue updated successfully.");

            await client.DeleteIssueAsync("YOUR-ISSUE-ID");
            Console.WriteLine("Issue deleted successfully.");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"An error occurred: {ex.Message}");
        }
    }
}