using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Models;
using Xunit;

public class ProgramTests
{
    private readonly JiraClient _client;

    public ProgramTests()
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");
        _client = client;
    }

    [Fact]
    public async Task CreateTaskAsync_Success()
    {
        await CreateTaskAsync("YOUR-PROJECT-KEY", "Test Task");
        var issues = await _client.SearchIssuesAsync(new SearchOptions { Jql = $"project = YOUR-PROJECT-KEY" });
        var task = issues.Items.FirstOrDefault(i => i.Key == client.GenerateIssueKey("YOUR-PROJECT-KEY"));
        Assert.NotNull(task);
    }

    [Fact]
    public async Task CreateTaskAsync_Error()
    {
        await Assert.ThrowsAsync<Exception>(async () =>
        {
            await CreateTaskAsync("INVALID-PROJECT-KEY", "Test Task");
        });
    }

    // Adicionar testes para outras funções e métodos públicos
}