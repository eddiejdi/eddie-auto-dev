using System;
using System.Net.Http;
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

    public async Task SendEventAsync(string issueKey, string eventType, string eventData)
    {
        var url = $"{_jiraUrl}/rest/api/2/issue/{issueKey}/comment";
        var content = new StringContent($"{{\"body\": \"{eventData}\"}}", System.Text.Encoding.UTF8, "application/json");

        using (var client = new HttpClient())
        {
            client.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Basic", Convert.ToBase64String(Encoding.ASCII.GetBytes($"{_apiKey}:")));
            await client.PostAsync(url, content);
        }
    }

    public async Task MonitorActivityAsync(string issueKey)
    {
        var url = $"{_jiraUrl}/rest/api/2/issue/{issueKey}";
        using (var client = new HttpClient())
        {
            var response = await client.GetAsync(url);
            if (response.IsSuccessStatusCode)
            {
                Console.WriteLine("Issue is active.");
            }
            else
            {
                Console.WriteLine($"Issue is not active. Status code: {response.StatusCode}");
            }
        }
    }

    public static void Main(string[] args)
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-api-key");
        var issueKey = "ABC-123";

        // Send an event
        await jiraClient.SendEventAsync(issueKey, "TaskCompleted", "Task ABC-123 has been completed.");

        // Monitor activity
        await jiraClient.MonitorActivityAsync(issueKey);
    }
}