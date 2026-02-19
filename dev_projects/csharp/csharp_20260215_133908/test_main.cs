using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp;
using Xunit;

public class ProgramTests
{
    [Fact]
    public async Task CreateTaskAsync_Successful()
    {
        // Configuração do JiraSharp
        var jira = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Cria uma nova tarefa no Jira com valores válidos
        var task = await jira.CreateTaskAsync("New Task", "This is a new task created by the C# Agent.");

        // Verifica se a tarefa foi criada corretamente
        Assert.NotNull(task);
        Assert.NotEmpty(task.Id);
    }

    [Fact]
    public async Task CreateTaskAsync_ErrorHandling()
    {
        // Configuração do JiraSharp com valores inválidos
        var jira = new JiraClient("https://your-jira-instance.atlassian.net", "invalid-username", "invalid-password");

        try
        {
            await jira.CreateTaskAsync("New Task", "This is a new task created by the C# Agent.");
        }
        catch (Exception ex)
        {
            // Verifica se o erro é esperado
            Assert.StartsWith(ex.Message, "Failed to authenticate with Jira");
        }
    }

    [Fact]
    public async Task CreateTaskAsync_EdgeCases()
    {
        // Teste com valores limite
        var task = await jira.CreateTaskAsync("Task 100", "This is a very long task name that exceeds the maximum length allowed by Jira.");

        // Verifica se o tarefa foi criada corretamente
        Assert.NotNull(task);
        Assert.NotEmpty(task.Id);

        // Teste com string vazia
        var emptyTask = await jira.CreateTaskAsync("", "This is a task with an empty name.");

        // Verifica se o tarefa foi criada corretamente
        Assert.NotNull(emptyTask);
        Assert.NotEmpty(emptyTask.Id);
    }
}