using System;
using System.Net.Http;
using System.Threading.Tasks;
using Xunit;

public class JiraClientTests
{
    private readonly JiraClient _jiraClient;

    public JiraClientTests()
    {
        _jiraClient = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");
    }

    [Fact]
    public async Task CreateIssueAsync_Successful()
    {
        await _jiraClient.CreateIssueAsync("YOUR-PROJECT-KEY", "Task", "Initial task description");

        // Additional assertions can be added here if needed
    }

    [Fact]
    public async Task CreateIssueAsync_InvalidProjectKey()
    {
        try
        {
            await _jiraClient.CreateIssueAsync("INVALID-PROJECT-KEY", "Task", "Initial task description");
            Assert.Fail("Expected an exception to be thrown for invalid project key");
        }
        catch (HttpRequestException ex)
        {
            // Expected exception message can be added here if needed
        }
    }

    [Fact]
    public async Task UpdateIssueAsync_Successful()
    {
        await _jiraClient.UpdateIssueAsync("YOUR-ISSUE-KEY", "Updated task description");

        // Additional assertions can be added here if needed
    }

    [Fact]
    public async Task UpdateIssueAsync_InvalidIssueKey()
    {
        try
        {
            await _jiraClient.UpdateIssueAsync("INVALID-ISSUE-KEY", "Updated task description");
            Assert.Fail("Expected an exception to be thrown for invalid issue key");
        }
        catch (HttpRequestException ex)
        {
            // Expected exception message can be added here if needed
        }
    }

    [Fact]
    public async Task UpdateIssueAsync_InvalidSummary()
    {
        try
        {
            await _jiraClient.UpdateIssueAsync("YOUR-ISSUE-KEY", "");
            Assert.Fail("Expected an exception to be thrown for invalid summary");
        }
        catch (HttpRequestException ex)
        {
            // Expected exception message can be added here if needed
        }
    }

    [Fact]
    public async Task UpdateIssueAsync_InvalidDescription()
    {
        try
        {
            await _jiraClient.UpdateIssueAsync("YOUR-ISSUE-KEY", " ");
            Assert.Fail("Expected an exception to be thrown for invalid description");
        }
        catch (HttpRequestException ex)
        {
            // Expected exception message can be added here if needed
        }
    }

    [Fact]
    public async Task UpdateIssueAsync_InvalidAssignee()
    {
        try
        {
            await _jiraClient.UpdateIssueAsync("YOUR-ISSUE-KEY", "username");
            Assert.Fail("Expected an exception to be thrown for invalid assignee");
        }
        catch (HttpRequestException ex)
        {
            // Expected exception message can be added here if needed
        }
    }
}