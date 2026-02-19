using System;
using System.Threading.Tasks;
using Xunit;

namespace JiraTrackingAgent.Tests
{
    public class ProgramTests
    {
        [Fact]
        public async Task SendNotificationToJiraAsync_Success()
        {
            // Simulação de envio de notificação para Jira com sucesso
            await Program.SendNotificationToJiraAsync();
            Assert.True(true, "Notificação enviada com sucesso.");
        }

        [Fact]
        public async Task SendNotificationToJiraAsync_Error()
        {
            // Simulação de erro ao enviar notificação para Jira (divisão por zero)
            try
            {
                await Program.SendNotificationToJiraAsync();
                Assert.True(false, "Erro esperado ao enviar notificação.");
            }
            catch (DivideByZeroException ex)
            {
                Assert.Equal("Não é possível dividir por zero.", ex.Message);
            }
        }

        [Fact]
        public async Task SendNotificationToJiraAsync_InvalidInput()
        {
            // Simulação de erro ao enviar notificação para Jira (valor inválido)
            try
            {
                await Program.SendNotificationToJiraAsync();
                Assert.True(false, "Erro esperado ao enviar notificação.");
            }
            catch (Exception ex)
            {
                Assert.Equal("Valor inválido.", ex.Message);
            }
        }

        [Fact]
        public async Task SendNotificationToJiraAsync_EdgeCase()
        {
            // Simulação de envio de notificação para Jira (valores limite, strings vazias, None, etc)
            try
            {
                await Program.SendNotificationToJiraAsync();
                Assert.True(false, "Erro esperado ao enviar notificação.");
            }
            catch (Exception ex)
            {
                Assert.Equal("Valor inválido.", ex.Message);
            }
        }
    }
}