using System;
using System.Net.Http;
using System.Threading.Tasks;

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

    public async Task CreateIssueAsync(string projectKey, string issueType, string summary, string description)
    {
        var url = $"{_baseUrl}/rest/api/2/issue";
        var content = $"{{\"fields\": {{\"project\": {{\"key\": \"{projectKey}\"}}, \"summary\": \"{summary}\", \"description\": \"{description}\"}}}}";

        using (var client = new HttpClient())
        {
            client.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Basic", Convert.ToBase64String(Encoding.UTF8.GetBytes($"{_username}:{_password}")));

            var response = await client.PostAsync(url, new StringContent(content, Encoding.UTF8, "application/json"));

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
        var url = $"{_baseUrl}/rest/api/2/issue/{issueKey}";
        var content = $"{{\"fields\": {{\"summary\": \"{summary}\", \"description\": \"{description}\"}}}}";

        using (var client = new HttpClient())
        {
            client.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Basic", Convert.ToBase64String(Encoding.UTF8.GetBytes($"{_username}:{_password}")));

            var response = await client.PutAsync(url, new StringContent(content, Encoding.UTF8, "application/json"));

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
        var url = $"{_baseUrl}/rest/api/2/issue/{issueKey}";

        using (var client = new HttpClient())
        {
            client.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Basic", Convert.ToBase64String(Encoding.UTF8.GetBytes($"{_username}:{_password}")));

            var response = await client.DeleteAsync(url);

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
        var url = $"{_baseUrl}/rest/api/2/issue/{issueKey}";

        using (var client = new HttpClient())
        {
            client.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Basic", Convert.ToBase64String(Encoding.UTF8.GetBytes($"{_username}:{_password}")));

            var response = await client.GetAsync(url);

            if (response.IsSuccessStatusCode)
            {
                Console.WriteLine(response.Content.ReadAsStringAsync());
            }
            else
            {
                Console.WriteLine($"Failed to get issue. Status code: {response.StatusCode}");
            }
        }
    }

    public async Task Main(string[] args)
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        await jiraClient.CreateIssueAsync("YOUR-PROJECT-KEY", "Task", "Implement feature X", "Description of the task.");
        await jiraClient.UpdateIssueAsync("YOUR-PROJECT-KEY-TASK-1", "Updated Task", "Feature X is implemented.", "Updated description of the task.");
        await jiraClient.DeleteIssueAsync("YOUR-PROJECT-KEY-TASK-1");
    }
}