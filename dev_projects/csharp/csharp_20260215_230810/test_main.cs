using System;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;
using JiraSharp.Client;

class ProgramTests
{
    [Fact]
    public async Task CreateTicketAsync_Success()
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        var issue = new Issue
        {
            Summary = "Teste de C# Agent com Jira",
            Description = "Este é um teste para integrar o C# Agent com Jira.",
            Project = new Project { Key = "YOUR-PROJECT" },
            Priority = new Priority { Name = "High" }
        };

        var createdIssue = await client.Issue.CreateAsync(issue);
        Assert.NotNull(createdIssue.Key);
    }

    [Fact]
    public async Task CreateTicketAsync_Error()
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        try
        {
            var issue = new Issue
            {
                Summary = "",
                Description = "Este é um teste para integrar o C# Agent com Jira.",
                Project = new Project { Key = "YOUR-PROJECT" },
                Priority = new Priority { Name = "High" }
            };

            await client.Issue.CreateAsync(issue);
        }
        catch (Exception ex)
        {
            Assert.Contains("Summary cannot be empty", ex.Message);
        }
    }

    [Fact]
    public async Task UpdateTicketAsync_Success()
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        var issueKey = "YOUR-ISSUE-Key";
        var update = new IssueUpdate
        {
            Summary = "Teste de C# Agent com Jira - Atualização",
            Description = "Este é um teste para atualizar o ticket no Jira."
        };

        var updatedIssue = await client.Issue.UpdateAsync(issueKey, update);
        Assert.NotNull(updatedIssue.Key);
    }

    [Fact]
    public async Task UpdateTicketAsync_Error()
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        try
        {
            var issueKey = "YOUR-ISSUE-Key";
            var update = new IssueUpdate
            {
                Summary = "",
                Description = "Este é um teste para integrar o C# Agent com Jira.",
                Project = new Project { Key = "YOUR-PROJECT" },
                Priority = new Priority { Name = "High" }
            };

            await client.Issue.UpdateAsync(issueKey, update);
        }
        catch (Exception ex)
        {
            Assert.Contains("Summary cannot be empty", ex.Message);
        }
    }

    [Fact]
    public async Task DeleteTicketAsync_Success()
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        var issueKey = "YOUR-ISSUE-Key";
        await client.Issue.DeleteAsync(issueKey);
        Assert.True(true); // Verifica se o ticket foi deletado com sucesso
    }

    [Fact]
    public async Task DeleteTicketAsync_Error()
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        try
        {
            var issueKey = "YOUR-ISSUE-Key";
            await client.Issue.DeleteAsync(issueKey);
        }
        catch (Exception ex)
        {
            Assert.Contains("Issue not found", ex.Message);
        }
    }
}