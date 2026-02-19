using System;
using System.Net.Http;
using System.Threading.Tasks;
using Xunit;

public class JiraClientTests
{
    [Fact]
    public async Task CreateIssueAsync_Success()
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
        await jiraClient.CreateIssueAsync("YOUR_PROJECT_KEY", "BUG", "Description of the issue", "Additional details");
    }

    [Fact]
    public async Task CreateIssueAsync_Error_InvalidProjectKey()
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
        await Assert.ThrowsAsync<Exception>(async () => await jiraClient.CreateIssueAsync("INVALID_PROJECT_KEY", "BUG", "Description of the issue", "Additional details"));
    }

    [Fact]
    public async Task CreateIssueAsync_Error_InvalidIssueType()
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
        await Assert.ThrowsAsync<Exception>(async () => await jiraClient.CreateIssueAsync("YOUR_PROJECT_KEY", "INVALID_ISSUE_TYPE", "Description of the issue", "Additional details"));
    }

    [Fact]
    public async Task CreateIssueAsync_Error_InvalidSummary()
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
        await Assert.ThrowsAsync<Exception>(async () => await jiraClient.CreateIssueAsync("YOUR_PROJECT_KEY", "BUG", "", "Additional details"));
    }

    [Fact]
    public async Task CreateIssueAsync_Error_InvalidDescription()
    {
        var jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
        await Assert.ThrowsAsync<Exception>(async () => await jiraClient.CreateIssueAsync("YOUR_PROJECT_KEY", "BUG", "Description of the issue", ""));
    }

    [Fact]
    public async Task SendEmailNotificationAsync_Success()
    {
        var emailNotificationClient = new EmailNotificationClient();
        await emailNotificationClient.SendEmailNotificationAsync("recipient@example.com", "New Issue", "A new issue has been created in Jira.");
    }

    [Fact]
    public async Task SendEmailNotificationAsync_Error_InvalidEmail()
    {
        var emailNotificationClient = new EmailNotificationClient();
        await Assert.ThrowsAsync<Exception>(async () => await emailNotificationClient.SendEmailNotificationAsync("INVALID_EMAIL", "New Issue", "A new issue has been created in Jira."));
    }

    [Fact]
    public async Task SendEmailNotificationAsync_Error_InvalidSubject()
    {
        var emailNotificationClient = new EmailNotificationClient();
        await Assert.ThrowsAsync<Exception>(async () => await emailNotificationClient.SendEmailNotificationAsync("recipient@example.com", "", "A new issue has been created in Jira."));
    }

    [Fact]
    public async Task SendEmailNotificationAsync_Error_InvalidBody()
    {
        var emailNotificationClient = new EmailNotificationClient();
        await Assert.ThrowsAsync<Exception>(async () => await emailNotificationClient.SendEmailNotificationAsync("recipient@example.com", "New Issue", "", ""));
    }
}