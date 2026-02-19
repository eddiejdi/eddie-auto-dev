using System;
using System.Net.Http;
using System.Threading.Tasks;

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

    public async Task CreateIssueAsync(string projectKey, string issueType, string summary)
    {
        var client = new HttpClient();
        var content = new FormUrlEncodedContent(new[]
        {
            new KeyValuePair<string, string>("jql", $"project={projectKey} AND type={issueType}"),
            new KeyValuePair<string, string>("fields[summary]", summary),
            new KeyValuePair<string, string>("fields[assignee]", "username"), // Replace with actual username
            new KeyValuePair<string, string>("fields[description]", "Description of the issue")
        });

        var response = await client.PostAsync($"{_jiraUrl}/rest/api/2.0/issue", content);
        response.EnsureSuccessStatusCode();
    }

    public async Task UpdateIssueAsync(string issueKey, string summary)
    {
        var client = new HttpClient();
        var content = new FormUrlEncodedContent(new[]
        {
            new KeyValuePair<string, string>("jql", $"key={issueKey}"),
            new KeyValuePair<string, string>("fields[summary]", summary),
            new KeyValuePair<string, string>("fields[assignee]", "username"), // Replace with actual username
            new KeyValuePair<string, string>("fields[description]", "Updated description of the issue")
        });

        var response = await client.PutAsync($"{_jiraUrl}/rest/api/2.0/issue", content);
        response.EnsureSuccessStatusCode();
    }
}

public class Program
{
    public static async Task Main(string[] args)
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        await jiraClient.CreateIssueAsync("YOUR-PROJECT-KEY", "Task", "Initial task description");
        await jiraClient.UpdateIssueAsync("YOUR-ISSUE-KEY", "Updated task description");
    }
}