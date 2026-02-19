using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        // Configuração do cliente Jira
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "username", "password");

        // Criar uma nova tarefa
        var task = new CreateTaskRequest
        {
            Summary = "Implement SCRUM-14",
            Description = "Integrar C# Agent com Jira - tracking de atividades em csharp.",
            Assignee = "user123"
        };

        var createdTask = await client.CreateTaskAsync(task);

        Console.WriteLine($"Tarefa criada: {createdTask.Key}");

        // Listar todas as tarefas do usuário
        var tasks = await client.GetTasksAsync("user123");

        foreach (var task in tasks)
        {
            Console.WriteLine($"Tarefa: {task.Key}");
        }

        // Atualizar uma tarefa
        var updateTaskRequest = new UpdateTaskRequest
        {
            Id = createdTask.Id,
            Summary = "Implement SCRUM-14 - Progresso"
        };

        await client.UpdateTaskAsync(updateTaskRequest);

        Console.WriteLine($"Tarefa atualizada: {createdTask.Key}");

        // Fechar uma tarefa
        var closeTaskRequest = new CloseTaskRequest
        {
            Id = createdTask.Id,
            Comment = "Fechada por user123"
        };

        await client.CloseTaskAsync(closeTaskRequest);

        Console.WriteLine($"Tarefa fechada: {createdTask.Key}");
    }
}