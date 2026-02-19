using System;
using System.Net.Http;
using System.Threading.Tasks;
using Newtonsoft.Json;

public class JiraClient
{
    private readonly string _baseUrl;
    private readonly string _username;
    private readonly string _password;

    public JiraClient(string baseUrl, string username, string password)
    {
        _baseUrl = baseUrl;
        _username = username;
        _password = password;
    }

    public async Task CreateIssueAsync(string projectKey, string summary, string description)
    {
        var issueData = new
        {
            fields = new
            {
                project = new { key = projectKey },
                summary = summary,
                description = description
            }
        };

        using (var httpClient = new HttpClient())
        {
            var content = new StringContent(JsonConvert.SerializeObject(issueData), Encoding.UTF8, "application/json");
            content.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Basic", Convert.ToBase64String(Encoding.ASCII.GetBytes($"{_username}:{_password}")));

            var response = await httpClient.PostAsync($"{_baseUrl}/rest/api/2/issue", content);

            if (response.IsSuccessStatusCode)
            {
                Console.WriteLine("Issue created successfully.");
            }
            else
            {
                Console.WriteLine($"Failed to create issue. Status code: {response.StatusCode}");
            }
        }
    }

    public async Task UpdateIssueAsync(string issueKey, string summary, string description)
    {
        var issueData = new
        {
            fields = new
            {
                summary = summary,
                description = description
            }
        };

        using (var httpClient = new HttpClient())
        {
            var content = new StringContent(JsonConvert.SerializeObject(issueData), Encoding.UTF8, "application/json");
            content.Headers.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Basic", Convert.ToBase64String(Encoding.ASCII.GetBytes($"{_username}:{_password}")));

            var response = await httpClient.PatchAsync($"{_baseUrl}/rest/api/2/issue/{issueKey}", content);

            if (response.IsSuccessStatusCode)
            {
                Console.WriteLine("Issue updated successfully.");
            }
            else
            {
                Console.WriteLine($"Failed to update issue. Status code: {response.StatusCode}");
            }
        }
    }

    public async Task DeleteIssueAsync(string issueKey)
    {
        using (var httpClient = new HttpClient())
        {
            var response = await httpClient.DeleteAsync($"{_baseUrl}/rest/api/2/issue/{issueKey}");

            if (response.IsSuccessStatusCode)
            {
                Console.WriteLine("Issue deleted successfully.");
            }
            else
            {
                Console.WriteLine($"Failed to delete issue. Status code: {response.StatusCode}");
            }
        }
    }

    public async Task GetIssueAsync(string issueKey)
    {
        using (var httpClient = new HttpClient())
        {
            var response = await httpClient.GetAsync($"{_baseUrl}/rest/api/2/issue/{issueKey}");

            if (response.IsSuccessStatusCode)
            {
                var content = await response.Content.ReadAsStringAsync();
                Console.WriteLine(content);
            }
            else
            {
                Console.WriteLine($"Failed to get issue. Status code: {response.StatusCode}");
            }
        }
    }
}

public class Program
{
    public static async Task Main(string[] args)
    {
        string baseUrl = "https://your-jira-instance.atlassian.net";
        string username = "your-username";
        string password = "your-password";

        var jiraClient = new JiraClient(baseUrl, username, password);

        await jiraClient.CreateIssueAsync("YOUR-PROJECT", "Test Issue", "This is a test issue.");
        await jiraClient.UpdateIssueAsync("YOUR-ISSUE", "Updated Test Issue", "This is an updated test issue.");
        await jiraClient.DeleteIssueAsync("YOUR-ISSUE");
        await jiraClient.GetIssueAsync("YOUR-ISSUE");
    }
}