using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using Xunit;

public class ProgramTests
{
    [Fact]
    public async Task CreateTaskAsync_Success()
    {
        // Configuração do cliente Jira
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        // Criar uma nova tarefa com valores válidos
        var task = new CreateTaskRequest
        {
            Summary = "Implement SCRUM-14",
            Description = "Integrar C# Agent com Jira - tracking de atividades em csharp.",
            Assignee = "user123"
        };

        var createdTask = await client.CreateTaskAsync(task);

        // Verificar se a tarefa foi criada corretamente
        Assert.NotNull(createdTask);
        Assert.NotEmpty(createdTask.Key);
    }

    [Fact]
    public async Task CreateTaskAsync_Failure_InvalidSummary()
    {
        // Configuração do cliente Jira
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        // Criar uma nova tarefa com um summary inválido
        var task = new CreateTaskRequest
        {
            Summary = "",
            Description = "Integrar C# Agent com Jira - tracking de atividades em csharp.",
            Assignee = "user123"
        };

        try
        {
            await client.CreateTaskAsync(task);
        }
        catch (Exception ex)
        {
            // Verificar se a exceção é do tipo InvalidRequestException
            Assert.IsType<InvalidRequestException>(ex);
            return;
        }

        // Se não lançou uma exceção, o teste falhou
        throw new Exception("A tarefa foi criada com sucesso, mas esperávamos um erro.");
    }
}