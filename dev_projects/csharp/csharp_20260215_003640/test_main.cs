using System;
using System.Threading.Tasks;
using JiraSharp;
using Xunit;

public class ProgramTests
{
    private readonly JiraClient _client;

    public ProgramTests()
    {
        // Configuração do cliente Jira (pode ser substituído pelo seu próprio código)
        _client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");
    }

    [Fact]
    public async Task CreateTicketAsync_Success()
    {
        var summary = "Teste C# Agent";
        var description = "Integração com Jira - tracking de atividades";

        await _client.Issue.CreateAsync(new Issue
        {
            Summary = summary,
            Description = description,
            ProjectKey = "YOUR_PROJECT_KEY",
            Priority = new Priority { Id = 1 }, // Prioridade alta
            Assignee = new Assignee { Username = "your-assignee-username" } // Colaborador
        });

        Console.WriteLine("Ticket criado com sucesso");
    }

    [Fact]
    public async Task CreateTicketAsync_Error()
    {
        await Assert.ThrowsAsync<Exception>(async () =>
        {
            await _client.Issue.CreateAsync(new Issue
            {
                Summary = "Teste C# Agent",
                Description = "",
                ProjectKey = "YOUR_PROJECT_KEY",
                Priority = new Priority { Id = 1 }, // Prioridade alta
                Assignee = new Assignee { Username = "your-assignee-username" } // Colaborador
            });
        });

        Console.WriteLine("Erro ao criar ticket");
    }

    [Fact]
    public async Task GetTicketAsync_Success()
    {
        var issueId = "YOUR_TICKET_ID"; // Substitua pelo ID do ticket criado no exemplo anterior

        var issue = await _client.Issue.GetAsync(issueId);

        Assert.NotNull(issue);
        Console.WriteLine("Detalhes do ticket:");
        Console.WriteLine($"ID: {issue.Id}");
        Console.WriteLine($"Summary: {issue.Summary}");
        Console.WriteLine($"Description: {issue.Description}");
    }

    [Fact]
    public async Task GetTicketAsync_Error()
    {
        await Assert.ThrowsAsync<Exception>(async () =>
        {
            await _client.Issue.GetAsync("INVALID_TICKET_ID");
        });

        Console.WriteLine("Erro ao buscar ticket inexistente");
    }
}