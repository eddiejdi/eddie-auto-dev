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
        try
        {
            var task = await client.CreateTaskAsync("New Task", "This is the description of the new task.");
            Console.WriteLine($"Task created: {task.Id}");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error creating task: {ex.Message}");
        }

        // Update the task
        try
        {
            await client.UpdateTaskAsync(task.Id, "Updated Task Description");
            Console.WriteLine($"Task updated: {task.Id}");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error updating task: {ex.Message}");
        }

        // Get all tasks
        try
        {
            var tasks = await client.GetTasksAsync();
            foreach (var t in tasks)
            {
                Console.WriteLine($"Task ID: {t.Id}, Summary: {t.Summary}");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error getting tasks: {ex.Message}");
        }

        // Close the task
        try
        {
            await client.CloseTaskAsync(task.Id);
            Console.WriteLine("Task closed.");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"Error closing task: {ex.Message}");
        }
    }
}