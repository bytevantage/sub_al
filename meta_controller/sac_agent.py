"""
Soft Actor-Critic (SAC) Agent for Strategy Ensemble Allocation
Continuous action space: 9-dimensional allocation vector
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np
from collections import deque
import random
from typing import Tuple, List
import os

from backend.core.logger import get_logger

logger = get_logger(__name__)


class PrioritizedReplayBuffer:
    """Prioritized Experience Replay Buffer"""
    
    def __init__(self, capacity: int = 100000, alpha: float = 0.6):
        self.capacity = capacity
        self.alpha = alpha
        self.buffer = deque(maxlen=capacity)
        self.priorities = deque(maxlen=capacity)
        self.position = 0
        
    def push(self, state, action, reward, next_state, done):
        """Add experience to buffer"""
        max_priority = max(self.priorities) if self.priorities else 1.0
        
        self.buffer.append((state, action, reward, next_state, done))
        self.priorities.append(max_priority)
        
    def sample(self, batch_size: int, beta: float = 0.4):
        """Sample batch with prioritized sampling"""
        if len(self.buffer) < batch_size:
            return None
        
        # Calculate sampling probabilities
        priorities = np.array(self.priorities)
        probabilities = priorities ** self.alpha
        probabilities /= probabilities.sum()
        
        # Sample indices
        indices = np.random.choice(len(self.buffer), batch_size, p=probabilities, replace=False)
        
        # Calculate importance-sampling weights
        total = len(self.buffer)
        weights = (total * probabilities[indices]) ** (-beta)
        weights /= weights.max()
        
        # Get experiences
        batch = [self.buffer[idx] for idx in indices]
        states, actions, rewards, next_states, dones = zip(*batch)
        
        return (
            np.array(states, dtype=np.float32),
            np.array(actions, dtype=np.float32),
            np.array(rewards, dtype=np.float32),
            np.array(next_states, dtype=np.float32),
            np.array(dones, dtype=np.float32),
            indices,
            weights
        )
    
    def update_priorities(self, indices, priorities):
        """Update priorities for sampled experiences"""
        for idx, priority in zip(indices, priorities):
            self.priorities[idx] = priority + 1e-6
    
    def __len__(self):
        return len(self.buffer)


class Actor(nn.Module):
    """Actor network for SAC - outputs mean and log_std for Gaussian policy"""
    
    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 256):
        super(Actor, self).__init__()
        
        self.fc1 = nn.Linear(state_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, hidden_dim)
        
        self.mean = nn.Linear(hidden_dim, action_dim)
        self.log_std = nn.Linear(hidden_dim, action_dim)
        
        self.action_dim = action_dim
        self.max_action = 0.35  # Max 35% per meta-group
        
        # Initialize weights
        self.apply(self._init_weights)
        
    def _init_weights(self, m):
        if isinstance(m, nn.Linear):
            nn.init.orthogonal_(m.weight, 1.0)
            nn.init.constant_(m.bias, 0.0)
    
    def forward(self, state):
        """Forward pass"""
        x = F.relu(self.fc1(state))
        x = F.relu(self.fc2(x))
        x = F.relu(self.fc3(x))
        
        mean = self.mean(x)
        log_std = self.log_std(x)
        log_std = torch.clamp(log_std, min=-20, max=2)
        
        return mean, log_std
    
    def sample(self, state):
        """Sample action from policy"""
        mean, log_std = self.forward(state)
        std = log_std.exp()
        
        # Reparameterization trick
        normal = torch.distributions.Normal(mean, std)
        x_t = normal.rsample()
        
        # Squash through tanh
        action = torch.tanh(x_t)
        
        # Compute log probability
        log_prob = normal.log_prob(x_t)
        log_prob -= torch.log(1 - action.pow(2) + 1e-6)
        log_prob = log_prob.sum(dim=-1, keepdim=True)
        
        # Apply softmax to ensure allocation sums to 1
        allocation = F.softmax(action, dim=-1)
        
        # Apply max constraint (clip each to 0.35)
        allocation = torch.clamp(allocation, max=self.max_action)
        allocation = allocation / allocation.sum(dim=-1, keepdim=True)  # Re-normalize
        
        return allocation, log_prob


class Critic(nn.Module):
    """Critic network for SAC - Q-function"""
    
    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int = 256):
        super(Critic, self).__init__()
        
        # Q1 network
        self.q1_fc1 = nn.Linear(state_dim + action_dim, hidden_dim)
        self.q1_fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.q1_fc3 = nn.Linear(hidden_dim, 1)
        
        # Q2 network
        self.q2_fc1 = nn.Linear(state_dim + action_dim, hidden_dim)
        self.q2_fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.q2_fc3 = nn.Linear(hidden_dim, 1)
        
        self.apply(self._init_weights)
        
    def _init_weights(self, m):
        if isinstance(m, nn.Linear):
            nn.init.orthogonal_(m.weight, 1.0)
            nn.init.constant_(m.bias, 0.0)
    
    def forward(self, state, action):
        """Forward pass through both Q-networks"""
        sa = torch.cat([state, action], dim=-1)
        
        # Q1
        q1 = F.relu(self.q1_fc1(sa))
        q1 = F.relu(self.q1_fc2(q1))
        q1 = self.q1_fc3(q1)
        
        # Q2
        q2 = F.relu(self.q2_fc1(sa))
        q2 = F.relu(self.q2_fc2(q2))
        q2 = self.q2_fc3(q2)
        
        return q1, q2


class SACAgent:
    """Soft Actor-Critic Agent for continuous action space"""
    
    def __init__(
        self,
        state_dim: int = 35,
        action_dim: int = 9,
        hidden_dim: int = 256,
        lr: float = 3e-4,
        gamma: float = 0.99,
        tau: float = 0.005,
        alpha: float = 0.2,
        buffer_size: int = 100000,
        device: str = "cpu"
    ):
        self.device = torch.device(device)
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.tau = tau
        self.alpha = alpha
        
        # Networks
        self.actor = Actor(state_dim, action_dim, hidden_dim).to(self.device)
        self.critic = Critic(state_dim, action_dim, hidden_dim).to(self.device)
        self.critic_target = Critic(state_dim, action_dim, hidden_dim).to(self.device)
        self.critic_target.load_state_dict(self.critic.state_dict())
        
        # Optimizers
        self.actor_optimizer = optim.Adam(self.actor.parameters(), lr=lr)
        self.critic_optimizer = optim.Adam(self.critic.parameters(), lr=lr)
        
        # Automatic entropy tuning
        self.target_entropy = -action_dim
        self.log_alpha = torch.zeros(1, requires_grad=True, device=self.device)
        self.alpha_optimizer = optim.Adam([self.log_alpha], lr=lr)
        
        # Replay buffer
        self.replay_buffer = PrioritizedReplayBuffer(buffer_size)
        
        # Training stats
        self.total_steps = 0
        self.training_steps = 0
        
        logger.info(f"SAC Agent initialized: state_dim={state_dim}, action_dim={action_dim}")
    
    def select_action(self, state: np.ndarray, deterministic: bool = False) -> np.ndarray:
        """Select action from policy"""
        state = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            if deterministic:
                mean, _ = self.actor(state)
                action = torch.tanh(mean)
                allocation = F.softmax(action, dim=-1)
            else:
                allocation, _ = self.actor.sample(state)
        
        return allocation.cpu().numpy()[0]
    
    def store_transition(self, state, action, reward, next_state, done):
        """Store transition in replay buffer"""
        self.replay_buffer.push(state, action, reward, next_state, done)
        self.total_steps += 1
    
    def train(self, batch_size: int = 256) -> dict:
        """Train the agent"""
        if len(self.replay_buffer) < batch_size:
            return {}
        
        # Sample from replay buffer
        beta = min(1.0, 0.4 + 0.6 * (self.training_steps / 100000))
        batch = self.replay_buffer.sample(batch_size, beta)
        
        if batch is None:
            return {}
        
        states, actions, rewards, next_states, dones, indices, weights = batch
        
        # Convert to tensors
        states = torch.FloatTensor(states).to(self.device)
        actions = torch.FloatTensor(actions).to(self.device)
        rewards = torch.FloatTensor(rewards).unsqueeze(1).to(self.device)
        next_states = torch.FloatTensor(next_states).to(self.device)
        dones = torch.FloatTensor(dones).unsqueeze(1).to(self.device)
        weights = torch.FloatTensor(weights).unsqueeze(1).to(self.device)
        
        # Update critic
        with torch.no_grad():
            next_actions, next_log_probs = self.actor.sample(next_states)
            q1_target, q2_target = self.critic_target(next_states, next_actions)
            q_target = torch.min(q1_target, q2_target)
            q_target = rewards + (1 - dones) * self.gamma * (q_target - self.alpha * next_log_probs)
        
        q1, q2 = self.critic(states, actions)
        critic_loss = (weights * (F.mse_loss(q1, q_target, reduction='none') + 
                                  F.mse_loss(q2, q_target, reduction='none'))).mean()
        
        self.critic_optimizer.zero_grad()
        critic_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.critic.parameters(), 1.0)
        self.critic_optimizer.step()
        
        # Update priorities
        td_errors = torch.abs(q1 - q_target).detach().cpu().numpy().flatten()
        self.replay_buffer.update_priorities(indices, td_errors)
        
        # Update actor
        new_actions, log_probs = self.actor.sample(states)
        q1_new, q2_new = self.critic(states, new_actions)
        q_new = torch.min(q1_new, q2_new)
        
        actor_loss = (self.alpha * log_probs - q_new).mean()
        
        self.actor_optimizer.zero_grad()
        actor_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.actor.parameters(), 1.0)
        self.actor_optimizer.step()
        
        # Update alpha (entropy temperature)
        alpha_loss = -(self.log_alpha * (log_probs + self.target_entropy).detach()).mean()
        
        self.alpha_optimizer.zero_grad()
        alpha_loss.backward()
        self.alpha_optimizer.step()
        
        self.alpha = self.log_alpha.exp().item()
        
        # Soft update target network
        for param, target_param in zip(self.critic.parameters(), self.critic_target.parameters()):
            target_param.data.copy_(self.tau * param.data + (1 - self.tau) * target_param.data)
        
        self.training_steps += 1
        
        return {
            'critic_loss': critic_loss.item(),
            'actor_loss': actor_loss.item(),
            'alpha': self.alpha,
            'q_value': q_new.mean().item()
        }
    
    def save(self, filepath: str):
        """Save model"""
        torch.save({
            'actor_state_dict': self.actor.state_dict(),
            'critic_state_dict': self.critic.state_dict(),
            'critic_target_state_dict': self.critic_target.state_dict(),
            'actor_optimizer_state_dict': self.actor_optimizer.state_dict(),
            'critic_optimizer_state_dict': self.critic_optimizer.state_dict(),
            'log_alpha': self.log_alpha,
            'alpha_optimizer_state_dict': self.alpha_optimizer.state_dict(),
            'total_steps': self.total_steps,
            'training_steps': self.training_steps
        }, filepath)
        logger.info(f"Model saved to {filepath}")
    
    def load(self, filepath: str):
        """Load model"""
        if not os.path.exists(filepath):
            logger.warning(f"Model file not found: {filepath}")
            return False
        
        checkpoint = torch.load(filepath, map_location=self.device)
        
        self.actor.load_state_dict(checkpoint['actor_state_dict'])
        self.critic.load_state_dict(checkpoint['critic_state_dict'])
        self.critic_target.load_state_dict(checkpoint['critic_target_state_dict'])
        self.actor_optimizer.load_state_dict(checkpoint['actor_optimizer_state_dict'])
        self.critic_optimizer.load_state_dict(checkpoint['critic_optimizer_state_dict'])
        self.log_alpha = checkpoint['log_alpha']
        self.alpha_optimizer.load_state_dict(checkpoint['alpha_optimizer_state_dict'])
        self.total_steps = checkpoint['total_steps']
        self.training_steps = checkpoint['training_steps']
        
        logger.info(f"Model loaded from {filepath}")
        return True
    
    def online_update(self, experience_buffer: List, num_updates: int = 50) -> dict:
        """
        Online learning update - fast replay of today's experience only
        Target: <60 seconds
        
        Args:
            experience_buffer: List of (state, action, reward, next_state, done) tuples
            num_updates: Number of gradient updates (default 50 for speed)
        
        Returns:
            dict: Training metrics
        """
        logger.info("="*80)
        logger.info("SAC ONLINE UPDATE")
        logger.info("="*80)
        logger.info(f"Experience samples: {len(experience_buffer)}")
        logger.info(f"Gradient updates: {num_updates}")
        
        # Add to replay buffer
        for experience in experience_buffer:
            self.replay_buffer.push(*experience)
        
        # Quick training loop
        metrics_list = []
        for _ in range(num_updates):
            metrics = self.train(batch_size=64)  # Smaller batch for speed
            if metrics:
                metrics_list.append(metrics)
        
        # Average metrics
        if metrics_list:
            avg_metrics = {
                'critic_loss': np.mean([m['critic_loss'] for m in metrics_list]),
                'actor_loss': np.mean([m['actor_loss'] for m in metrics_list]),
                'alpha': metrics_list[-1]['alpha'],
                'q_value': np.mean([m['q_value'] for m in metrics_list])
            }
        else:
            avg_metrics = {'critic_loss': 0, 'actor_loss': 0, 'alpha': self.alpha, 'q_value': 0}
        
        # Save updated model
        self.save('models/sac_prod_latest.pth')
        
        # Store critic loss for monitoring
        self._store_critic_loss(avg_metrics['critic_loss'])
        
        logger.info(f"✅ Online update complete")
        logger.info(f"   Critic loss: {avg_metrics['critic_loss']:.4f}")
        logger.info(f"   Actor loss: {avg_metrics['actor_loss']:.4f}")
        
        return avg_metrics
    
    def load_experience_buffer(self, date):
        """Load experience buffer from database for specific date"""
        from backend.database.connection import get_db_connection
        
        logger.info(f"Loading experience buffer for {date.strftime('%Y-%m-%d')}...")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Query experience data from database
        query = """
        SELECT state, action, reward, next_state, done
        FROM sac_experience
        WHERE DATE(timestamp) = %s
        ORDER BY timestamp
        """
        
        cursor.execute(query, (date.date(),))
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            logger.warning(f"No experience data found for {date.strftime('%Y-%m-%d')}")
            return []
        
        # Convert to list of tuples
        experience_buffer = []
        for row in rows:
            state = np.frombuffer(row[0], dtype=np.float32)
            action = np.frombuffer(row[1], dtype=np.float32)
            reward = float(row[2])
            next_state = np.frombuffer(row[3], dtype=np.float32)
            done = bool(row[4])
            experience_buffer.append((state, action, reward, next_state, done))
        
        logger.info(f"   Loaded {len(experience_buffer)} experiences")
        
        return experience_buffer
    
    def _store_critic_loss(self, loss: float):
        """Store critic loss for monitoring"""
        from datetime import datetime
        from backend.database.connection import get_db_connection
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sac_critic_loss_history (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP NOT NULL,
                critic_loss FLOAT NOT NULL
            )
        """)
        
        cursor.execute("""
            INSERT INTO sac_critic_loss_history (timestamp, critic_loss)
            VALUES (%s, %s)
        """, (datetime.now(), loss))
        
        conn.commit()
        conn.close()
    
    def get_previous_critic_loss(self) -> float:
        """Get yesterday's average critic loss for comparison"""
        from datetime import datetime, timedelta
        from backend.database.connection import get_db_connection
        
        yesterday = datetime.now() - timedelta(days=1)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT AVG(critic_loss)
            FROM sac_critic_loss_history
            WHERE DATE(timestamp) = %s
        """, (yesterday.date(),))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            return float(result[0])
        
        return None
