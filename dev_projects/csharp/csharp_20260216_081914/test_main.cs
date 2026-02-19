using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;
using JiraSharp.Model;
using NUnit.Framework;

[TestFixture]
public class JiraSharpClientTests
{
    private readonly JiraSharpClient _jiraClient;

    public JiraSharpClientTests()
    {
        _jiraClient = new JiraSharpClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");
    }

    [Test]
    public async Task CreateTask_Successful()
    {
        var task = new Task
        {
            Summary = "Teste Tarefa",
            Description = "Descrição da tarefa para teste.",
            Priority = Priority.High,
            Assignee = new User { Name = "assignee-name" }
        };

        await _jiraClient.CreateTask(task);
        Console.WriteLine("Tarefa criada com sucesso!");
    }

    [Test]
    public async Task CreateTask_InvalidSummary()
    {
        var task = new Task
        {
            Summary = "",
            Description = "Descrição da tarefa para teste.",
            Priority = Priority.High,
            Assignee = new User { Name = "assignee-name" }
        };

        try
        {
            await _jiraClient.CreateTask(task);
            Assert.Fail("Deveria lançar uma exceção de validação.");
        }
        catch (ArgumentException)
        {
            Console.WriteLine("Exceção correta lançada para tarefa com summary inválido.");
        }
    }

    [Test]
    public async Task CreateTask_InvalidDescription()
    {
        var task = new Task
        {
            Summary = "Teste Tarefa",
            Description = "",
            Priority = Priority.High,
            Assignee = new User { Name = "assignee-name" }
        };

        try
        {
            await _jiraClient.CreateTask(task);
            Assert.Fail("Deveria lançar uma exceção de validação.");
        }
        catch (ArgumentException)
        {
            Console.WriteLine("Exceção correta lançada para tarefa com description inválida.");
        }
    }

    [Test]
    public async Task CreateTask_InvalidPriority()
    {
        var task = new Task
        {
            Summary = "Teste Tarefa",
            Description = "Descrição da tarefa para teste.",
            Priority = (Priority)10, // Valor inválido
            Assignee = new User { Name = "assignee-name" }
        };

        try
        {
            await _jiraClient.CreateTask(task);
            Assert.Fail("Deveria lançar uma exceção de validação.");
        }
        catch (ArgumentException)
        {
            Console.WriteLine("Exceção correta lançada para tarefa com priority inválida.");
        }
    }

    [Test]
    public async Task CreateTask_InvalidAssignee()
    {
        var task = new Task
        {
            Summary = "Teste Tarefa",
            Description = "Descrição da tarefa para teste.",
            Priority = Priority.High,
            Assignee = null // Valor inválido
        };

        try
        {
            await _jiraClient.CreateTask(task);
            Assert.Fail("Deveria lançar uma exceção de validação.");
        }
        catch (ArgumentException)
        {
            Console.WriteLine("Exceção correta lançada para tarefa com assignee inválido.");
        }
    }

    [Test]
    public async Task CreateTask_InvalidTaskId()
    {
        var task = new Task
        {
            Summary = "Teste Tarefa",
            Description = "Descrição da tarefa para teste.",
            Priority = Priority.High,
            Assignee = new User { Name = "assignee-name" }
        };

        try
        {
            await _jiraClient.CreateTask(task);
            Assert.Fail("Deveria lançar uma exceção de validação.");
        }
        catch (ArgumentException)
        {
            Console.WriteLine("Exceção correta lançada para tarefa com taskId inválido.");
        }
    }

    [Test]
    public async Task MonitorTask_Successful()
    {
        var task = await _jiraClient.GetTask("12345");
        Console.WriteLine($"Título: {task.Summary}");
        Console.WriteLine($"Descrição: {task.Description}");
        Console.WriteLine($"Prioridade: {task.Priority}");
        Console.WriteLine($"Atribuído a: {task.Assignee.Name}");
    }

    [Test]
    public async Task MonitorTask_TaskNotFound()
    {
        try
        {
            await _jiraClient.GetTask("67890");
            Assert.Fail("Deveria lançar uma exceção de validação.");
        }
        catch (ArgumentException)
        {
            Console.WriteLine("Exceção correta lançada para tarefa não encontrada.");
        }
    }

    [Test]
    public async Task ManageTasks_Successful()
    {
        var tasks = await _jiraClient.GetTasks();
        foreach (var task in tasks)
        {
            Console.WriteLine($"Título: {task.Summary}");
        }
    }

    [Test]
    public async Task ManageTasks_NoTasksFound()
    {
        try
        {
            await _jiraClient.GetTasks();
            Assert.Fail("Deveria lançar uma exceção de validação.");
        }
        catch (ArgumentException)
        {
            Console.WriteLine("Exceção correta lançada para lista vazia de tarefas.");
        }
    }
}