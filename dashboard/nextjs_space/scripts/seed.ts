import { PrismaClient } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

async function main() {
  const hashedPassword = await bcrypt.hash('5UkThB#G1n', 12);
  await prisma.user.upsert({
    where: { email: 'abacus-f7b6e4e1@example.com' },
    update: {},
    create: {
      email: 'abacus-f7b6e4e1@example.com',
      password: hashedPassword,
      name: 'Admin',
      role: 'admin',
    },
  });
  console.log('Seed complete');
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
