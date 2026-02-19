using System;
using System.Net.Http;
using System.Threading.Tasks;

// Define a class to represent the Jira API
public class JiraClient
{
    private readonly string _jiraUrl;
    private readonly string _username;
    private readonly string _password;

    public JiraClient(string jiraUrl, string username, string password)
    {
        _jiraUrl = jiraUrl;
        _username = username;
        _password = password;
    }

    // Method to create a new issue in Jira
    public async Task CreateIssueAsync(string summary, string description, string projectKey)
    {
        var client = new HttpClient();
        var url = $"{_jiraUrl}/rest/api/2/issue";

        var requestBody = new
        {
            fields = new
            {
                project = new { key = projectKey },
                summary = summary,
                description = description,
                issuetype = new { name = "Task" }
            }
        };

        var content = new StringContent(JsonConvert.SerializeObject(requestBody), System.Text.Encoding.UTF8, "application/json");

        try
        {
            var response = await client.PostAsync(url, content);
            response.EnsureSuccessStatusCode();

            Console.WriteLine("Issue created successfully.");
        }
        catch (HttpRequestException ex)
        {
            Console.WriteLine($"Error creating issue: {ex.Message}");
        }
    }
}

// Example usage of the JiraClient class
class Program
{
    static async Task Main(string[] args)
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        await jiraClient.CreateIssueAsync("New Feature Request", "Implement a new feature in the application.", "YOUR-PROJECT-KEY");
    }
}