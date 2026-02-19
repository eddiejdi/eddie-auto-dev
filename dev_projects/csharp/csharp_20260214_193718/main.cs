using System;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;

public class JiraClient
{
    private readonly string _jiraUrl;
    private readonly string _apiKey;

    public JiraClient(string jiraUrl, string apiKey)
    {
        _jiraUrl = jiraUrl;
        _apiKey = apiKey;
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

        using (var httpClient = new HttpClient())
        {
            httpClient.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Basic", _apiKey);
            var content = new StringContent(JsonSerializer.Serialize(requestBody), Encoding.UTF8, "application/json");

            var response = await httpClient.PostAsync($"{_jiraUrl}/rest/api/2/issue", content);

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

    public async Task GetIssuesAsync(string projectKey, string status = null)
    {
        var queryParams = new Dictionary<string, string>
        {
            ["jql"] = $"project = {projectKey} AND status = {status}"
        };

        using (var httpClient = new HttpClient())
        {
            var queryString = "?" + string.Join("&", queryParams.Select(kv => $"{kv.Key}={kv.Value}"));
            var response = await httpClient.GetAsync($"{_jiraUrl}/rest/api/2/search?{queryString}");

            if (response.IsSuccessStatusCode)
            {
                var responseBody = await response.Content.ReadAsStringAsync();
                Console.WriteLine(responseBody);
            }
            else
            {
                Console.WriteLine($"Failed to retrieve issues. Status code: {response.StatusCode}");
            }
        }
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

        using (var httpClient = new HttpClient())
        {
            httpClient.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Basic", _apiKey);
            var content = new StringContent(JsonSerializer.Serialize(requestBody), Encoding.UTF8, "application/json");

            var response = await httpClient.PutAsync($"{_jiraUrl}/rest/api/2/issue/{issueKey}", content);

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
            httpClient.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Basic", _apiKey);
            var response = await httpClient.DeleteAsync($"{_jiraUrl}/rest/api/2/issue/{issueKey}");

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

    public async Task NotifyWebhookAsync(string webhookUrl, string payload)
    {
        using (var httpClient = new HttpClient())
        {
            var content = new StringContent(payload, Encoding.UTF8, "application/json");
            var response = await httpClient.PostAsync(webhookUrl, content);

            if (response.IsSuccessStatusCode)
            {
                Console.WriteLine("Webhook notification sent successfully.");
            }
            else
            {
                Console.WriteLine($"Failed to send webhook notification. Status code: {response.StatusCode}");
            }
        }
    }

    public async Task Main(string[] args)
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-api-key");

        await jiraClient.CreateIssueAsync("YOUR-PROJECT-KEY", "Task", "Implement a feature in C#", "This is the task description.");
        await jiraClient.GetIssuesAsync("YOUR-PROJECT-KEY");
        await jiraClient.UpdateIssueAsync("YOUR-ISSUE-ID", "Updated Task", "This is the updated task description.");
        await jiraClient.DeleteIssueAsync("YOUR-ISSUE-ID");
        await jiraClient.NotifyWebhookAsync("https://your-webhook-url.com/webhook", "{\"message\": \"New issue created\"}");
    }
}