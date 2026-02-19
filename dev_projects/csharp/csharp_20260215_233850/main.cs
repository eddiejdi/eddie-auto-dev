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

    public async Task CreateIssueAsync(string projectKey, string issueType, string summary, string description)
    {
        var url = $"{_jiraUrl}/rest/api/2/issue";
        var content = new StringContent($"{{\"fields\":{{\"project\":{\"key\":\"{projectKey}\"},\"issuetype\":{\"name\":\"{issueType}\"},\"summary\":\"{summary}\",\"description\":\"{description}\"}}}}", System.Text.Encoding.UTF8, "application/json");

        using (var client = new HttpClient())
        {
            client.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Basic", Convert.ToBase64String(System.Text.Encoding.UTF8.GetBytes($"{_username}:{_password}")));

            var response = await client.PostAsync(url, content);

            if (!response.IsSuccessStatusCode)
            {
                throw new Exception($"Failed to create issue: {await response.Content.ReadAsStringAsync()}");
            }
        }
    }

    public async Task SendEmailNotificationAsync(string email, string subject, string body)
    {
        using (var client = new HttpClient())
        {
            var url = "https://api.sendgrid.com/v3/mail/send";
            var content = new StringContent($"{{\"personalizations\": [{{\"to\": [{{\"email\":\"{email}\"}}]]}},\"from\": {{\"email\":\"your-email@example.com\"}},\"subject\":\"{subject}\",\"content\": [{{\"type\":\"text/plain\",\"value\":\"{body}\"}}]}}", System.Text.Encoding.UTF8, "application/json");

            client.DefaultRequestHeaders.Authorization = new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", "YOUR_SENDGRID_API_KEY"));

            var response = await client.PostAsync(url, content);

            if (!response.IsSuccessStatusCode)
            {
                throw new Exception($"Failed to send email: {await response.Content.ReadAsStringAsync()}");
            }
        }
    }
}

public class Program
{
    public static async Task Main(string[] args)
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
        await jiraClient.CreateIssueAsync("YOUR_PROJECT_KEY", "BUG", "Description of the issue", "Additional details");

        var emailNotificationClient = new EmailNotificationClient();
        await emailNotificationClient.SendEmailNotificationAsync("recipient@example.com", "New Issue", "A new issue has been created in Jira.");
    }
}