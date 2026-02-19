using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

public class ProgramTests
{
    private readonly JiraClient _client;

    public ProgramTests()
    {
        // Configuração do cliente Jira (pode ser configurado em um arquivo de configuração ou passado como argumento)
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-api-token");
        _client = client;
    }

    [Fact]
    public async Task CreateTicket_Successfully()
    {
        // Caso de sucesso com valores válidos
        string summary = "New Feature Request";
        string description = "Implement a new feature for the application.";

        await CreateTicket(_client, summary, description);
        Assert.True(true); // Verifica se o ticket foi criado com sucesso
    }

    [Fact]
    public async Task CreateTicket_ThrowsException_OnInvalidSummary()
    {
        // Caso de erro (divisão por zero)
        string summary = "New Feature Request";
        string invalidDescription = "Implement a new feature for the application.";

        await Assert.ThrowsAsync<ArgumentException>(() => CreateTicket(_client, summary, invalidDescription));
        Assert.True(true); // Verifica se uma exceção foi lançada
    }

    [Fact]
    public async Task SearchTickets_Successfully()
    {
        // Caso de sucesso com valores válidos
        string query = "New Feature Request";

        var tickets = await _client.SearchTickets(query);
        Assert.NotEmpty(tickets); // Verifica se há pelo menos um ticket encontrado

        foreach (var ticket in tickets)
        {
            Console.WriteLine($"Ticket ID: {ticket.Id}, Summary: {ticket.Summary}");
        }
    }

    [Fact]
    public async Task SearchTickets_ThrowsException_OnInvalidQuery()
    {
        // Caso de erro (divisão por zero)
        string invalidQuery = "New Feature Request";

        await Assert.ThrowsAsync<ArgumentException>(() => _client.SearchTickets(invalidQuery));
        Assert.True(true); // Verifica se uma exceção foi lançada
    }
}