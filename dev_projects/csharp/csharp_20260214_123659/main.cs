using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using JiraSharp.Client;

class Program
{
    static async Task Main(string[] args)
    {
        var client = new JiraClient("https://your-jira-instance.atlassian.net", "your-username", "your-password");

        // Create a task
        var task = await client.CreateTaskAsync("New Task", "This is the description of the new task.");

        Console.WriteLine($"Task created: {task.Id}");

        // Update the task
        await client.UpdateTaskAsync(task.Id, "Updated Task Description");

        Console.WriteLine($"Task updated: {task.Id}");

        // Get all tasks
        var tasks = await client.GetTasksAsync();

        foreach (var t in tasks)
        {
            Console.WriteLine($"Task ID: {t.Id}, Summary: {t.Summary}");
        }

        // Close the task
        await client.CloseTaskAsync(task.Id);

        Console.WriteLine("Task closed.");
    }
}