# -*- coding: utf-8 -*-
"""
Módulo M1 — cache de blocos (buffer cache).

Referência: Silberschatz, 9ª ed., 13.4.3 (Caching) e 12.6 (Efficiency and Performance) — pesquisa.

Implementem CacheLRU e CacheFIFO com a interface abaixo. O simulador de E/S chama:

    ler(bloco) -> bool
        True se o bloco está na cache (acerto). Num acerto, a LRU atualiza a recência;
        a FIFO não muda nada.
    inserir(bloco) -> list[int]
        Chamado depois de uma falta de leitura, quando o bloco chega do disco. Se a cache
        estiver cheia, expulsa uma vítima (LRU: a usada há mais tempo; FIFO: a que entrou
        primeiro). Devolve os blocos SUJOS expulsos, que o simulador vai gravar no disco.
    escrever(bloco) -> list[int]
        Escrita do usuário. Coloca (ou atualiza) o bloco na cache e devolve a lista de blocos
        que precisam ser gravados no disco AGORA:
          write-through: o próprio bloco (+ sujos expulsos, que não existem nesta política);
          write-back:    só os blocos sujos expulsos; o bloco escrito fica marcado como sujo.
        Uma escrita conta como acesso para a LRU.
    sincronizar() -> list[int]
        Gravação periódica (a cada INTERVALO_SYNC_MS): devolve todos os blocos sujos e os
        marca como limpos.
    sujos() -> int
        Quantos blocos estão sujos agora (usado para medir a perda numa queda de energia).

Política de escrita: 'write-through' ou 'write-back'.
"""


from collections import OrderedDict


class Cache:
    nome = "?"

    def __init__(self, capacidade, escrita="write-back"):
        if escrita not in ("write-through", "write-back"):
            raise ValueError("escrita deve ser 'write-through' ou 'write-back'")
        self.capacidade = capacidade
        self.escrita = escrita
        self.blocos = OrderedDict()  # bloco -> bool (True se sujo)

    def ler(self, bloco):
        raise NotImplementedError

    def inserir(self, bloco):
        raise NotImplementedError

    def escrever(self, bloco):
        raise NotImplementedError

    def sincronizar(self):
        sujos = [b for b, s in self.blocos.items() if s]
        for b in sujos:
            self.blocos[b] = False
        return sujos

    def sujos(self):
        return sum(1 for s in self.blocos.values() if s)


class CacheLRU(Cache):
    nome = "LRU"

    def ler(self, bloco):
        if bloco in self.blocos:
            self.blocos.move_to_end(bloco)
            return True
        return False

    def inserir(self, bloco):
        if bloco in self.blocos:
            self.blocos.move_to_end(bloco)
            return []
        expulsos = []
        if len(self.blocos) >= self.capacidade:
            vitima, sujo = self.blocos.popitem(last=False)
            if sujo:
                expulsos.append(vitima)
        self.blocos[bloco] = False
        return expulsos

    def escrever(self, bloco):
        expulsos = []
        if bloco in self.blocos:
            self.blocos.move_to_end(bloco)
        else:
            if len(self.blocos) >= self.capacidade:
                vitima, sujo = self.blocos.popitem(last=False)
                if sujo:
                    expulsos.append(vitima)
        if self.escrita == "write-through":
            self.blocos[bloco] = False
            return [bloco] + expulsos
        else:
            self.blocos[bloco] = True
            return expulsos


class CacheFIFO(Cache):
    nome = "FIFO"

    def ler(self, bloco):
        return bloco in self.blocos

    def inserir(self, bloco):
        if bloco in self.blocos:
            return []
        expulsos = []
        if len(self.blocos) >= self.capacidade:
            vitima, sujo = self.blocos.popitem(last=False)
            if sujo:
                expulsos.append(vitima)
        self.blocos[bloco] = False
        return expulsos

    def escrever(self, bloco):
        expulsos = []
        if bloco not in self.blocos and len(self.blocos) >= self.capacidade:
            vitima, sujo = self.blocos.popitem(last=False)
            if sujo:
                expulsos.append(vitima)
        if self.escrita == "write-through":
            self.blocos[bloco] = False
            return [bloco] + expulsos
        else:
            self.blocos[bloco] = True
            return expulsos


CACHES = {"LRU": CacheLRU, "FIFO": CacheFIFO}


def criar_cache(nome, capacidade, escrita):
    try:
        return CACHES[nome](capacidade, escrita)
    except KeyError:
        raise ValueError("cache desconhecida: %s" % nome)
